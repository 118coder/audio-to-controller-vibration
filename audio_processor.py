#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频处理模块
实现实时音频采集、频谱分析和信号处理
"""

# 优先使用 PyAudioWPatch（PyAudio 的 WASAPI 环回分支）：
# 它能直接采集"系统正在播放的声音"，不需要用户去启用"立体声混音"虚拟设备。
try:
    import pyaudiowpatch as pyaudio
    HAS_WASAPI_LOOPBACK = True
except ImportError:
    import pyaudio
    HAS_WASAPI_LOOPBACK = False

import numpy as np
from scipy import signal
from scipy.fft import fft
import threading
import queue
import time

class AudioProcessor:
    def __init__(self, sample_rate=44100, chunk_size=1024, device_index=None):
        """
        初始化音频处理器
        
        Args:
            sample_rate: 采样率，默认44100Hz（实际会以设备支持值为准）
            chunk_size: 音频块大小，默认1024（减小以降低延迟）
            device_index: 音频设备索引，None为默认设备（优先取 WASAPI 环回=系统音频）
        """
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.device_index = device_index
        
        # 音频流相关
        self.audio = None
        self.stream = None
        self.is_recording = False
        
        # 实际采集参数（以成功打开流时为准）
        self.capture_format = pyaudio.paFloat32
        self.capture_channels = 1
        self.capture_is_loopback = False
        self.last_error = None
        
        # 数据队列 - 减小队列大小以降低延迟
        self.audio_queue = queue.Queue(maxsize=3)
        self.volume_window_size = 3
        
        # 频谱分析参数
        self.window = np.hanning(chunk_size)
        
        # 多频段滤波器设置（用于精细频率分析）
        self.frequency_bands = {
            'sub_bass': (20, 60),      # 超低频：爆炸、雷声
            'bass': (60, 200),         # 低频：打击乐、低音
            'low_mid': (200, 500),     # 中低频：人声、吉他
            'mid': (500, 2000),        # 中频：人声主体
            'high_mid': (2000, 6000),  # 中高频：清晰度、细节
            'treble': (6000, 16000)    # 高频：金属声、尖锐音
        }
        
        # 为每个频段创建滤波器（采样率变化时会整体重建）
        self.band_filters = {}
        self.lowpass_filter = None
        self.highpass_filter = None
        self._rebuild_filters(self.sample_rate)
        
        # 音量分析窗口
        self.volume_buffer = []

    def _rebuild_filters(self, sample_rate):
        """按实际采样率重建滤波器（WASAPI 设备常是 48kHz，仍按 44.1kHz 算会切错频段）"""
        self.sample_rate = int(sample_rate)
        self.band_filters = {}
        for band_name, (low_freq, high_freq) in self.frequency_bands.items():
            self.band_filters[band_name] = self._create_bandpass_filter(low_freq, high_freq)
        self.lowpass_filter = self._create_lowpass_filter(300)
        self.highpass_filter = self._create_highpass_filter(300)
        print(f"✓ 滤波器已按 {self.sample_rate} Hz 重建")
        
        
    def _create_lowpass_filter(self, cutoff_freq):
        """创建低通滤波器"""
        nyquist = self.sample_rate / 2
        normalized_cutoff = cutoff_freq / nyquist
        b, a = signal.butter(4, normalized_cutoff, btype='low')
        return (b, a)
    
    def _create_highpass_filter(self, cutoff_freq):
        """创建高通滤波器"""
        nyquist = self.sample_rate / 2
        normalized_cutoff = cutoff_freq / nyquist
        b, a = signal.butter(4, normalized_cutoff, btype='high')
        return (b, a)
    
    def _create_bandpass_filter(self, low_freq, high_freq):
        """创建带通滤波器"""
        nyquist = self.sample_rate / 2
        low_normalized = low_freq / nyquist
        high_normalized = high_freq / nyquist
        
        # 确保频率在有效范围内
        low_normalized = max(0.001, min(0.999, low_normalized))
        high_normalized = max(0.001, min(0.999, high_normalized))
        
        if low_normalized >= high_normalized:
            high_normalized = low_normalized + 0.01
            
        b, a = signal.butter(4, [low_normalized, high_normalized], btype='band')
        return (b, a)
    
    def get_audio_devices(self):
        """获取可用的音频设备列表（含 WASAPI 环回 = 真正的系统音频）"""
        if not self.audio:
            self.audio = pyaudio.PyAudio()
        
        devices = []
        for i in range(self.audio.get_device_count()):
            try:
                device_info = self.audio.get_device_info_by_index(i)
            except Exception:
                continue
            if device_info.get('maxInputChannels', 0) <= 0:  # 只显示可采集的设备
                continue
            
            device_name = device_info['name']
            is_loopback = bool(device_info.get('isLoopbackDevice', False))
            device_type = 'wasapi_loopback' if is_loopback else self._classify_device_type(device_name)
            
            devices.append({
                'index': i,
                'name': device_name,
                'type': device_type,
                'channels': device_info['maxInputChannels'],
                'sample_rate': device_info['defaultSampleRate'],
                'is_system_audio': is_loopback or device_type in ['stereo_mix', 'what_you_hear', 'loopback'],
                'is_loopback': is_loopback
            })
        
        # 当前默认输出的环回设备（就是用户现在正在听的那个）排最前
        default_loopback_index = None
        if HAS_WASAPI_LOOPBACK:
            try:
                default_loopback_index = self.audio.get_default_wasapi_loopback()['index']
            except Exception:
                default_loopback_index = None
        for d in devices:
            d['is_default_loopback'] = (d['index'] == default_loopback_index)

        devices.sort(key=lambda x: (
            0 if x['index'] == default_loopback_index else (1 if x['is_system_audio'] else 2),
            x['name']
        ))
        
        # 去重：同一设备会被不同 Host API（MME/DirectSound/WASAPI）重复列出，只留第一个
        seen, unique_devices = set(), []
        for d in devices:
            key = (d['name'].strip().lower(), d['is_loopback'])
            if key in seen:
                continue
            seen.add(key)
            unique_devices.append(d)
        return unique_devices
    
    def _classify_device_type(self, device_name):
        """分类设备类型"""
        device_name_lower = device_name.lower()
        
        # 系统音频捕获设备的常见名称
        system_audio_keywords = [
            'stereo mix', '立体声混音', 'stereomix',
            'what you hear', 'what u hear', 'wave out mix',
            'sum', 'loopback', '您听到的声音',
            'speakers', '扬声器', 'output', '输出',
            'playback', '播放', 'render', '呈现'
        ]
        
        microphone_keywords = [
            'microphone', 'mic', '麦克风', '话筒',
            'input', '输入', 'capture', '捕获'
        ]
        
        for keyword in system_audio_keywords:
            if keyword in device_name_lower:
                if 'stereo mix' in device_name_lower or '立体声混音' in device_name_lower:
                    return 'stereo_mix'
                elif 'what you hear' in device_name_lower or '您听到的声音' in device_name_lower:
                    return 'what_you_hear'
                else:
                    return 'loopback'
        
        for keyword in microphone_keywords:
            if keyword in device_name_lower:
                return 'microphone'
        
        return 'unknown'
    
    def _resolve_capture_device(self):
        """确定要采集的设备信息；None 时优先用 WASAPI 环回（= 系统正在播放的声音）"""
        info = None
        device_index = self.device_index
        
        if device_index is None:
            if HAS_WASAPI_LOOPBACK:
                try:
                    lb = self.audio.get_default_wasapi_loopback()
                    if lb:
                        device_index = lb['index']
                        info = lb
                        print(f"未指定设备，自动使用系统音频(WASAPI环回): {lb.get('name')}")
                except Exception as e:
                    print(f"获取默认 WASAPI 环回设备失败: {e}")
            if device_index is None:
                try:
                    info = self.audio.get_default_input_device_info()
                    device_index = int(info['index'])
                except Exception:
                    info = None
        else:
            try:
                info = self.audio.get_device_info_by_index(device_index)
            except Exception:
                info = None
        
        return device_index, info
    
    def start_recording(self, callback=None):
        """开始音频录制（自动匹配设备真正支持的通道数/采样率/格式）"""
        if self.is_recording:
            return False
        
        try:
            if not self.audio:
                self.audio = pyaudio.PyAudio()
            
            device_index, info = self._resolve_capture_device()
            is_loopback = bool(info.get('isLoopbackDevice', False)) if info else False
            
            # WASAPI 环回设备必须用它的原生通道数（一般 2），普通输入按单声道采集
            max_ch = int(info.get('maxInputChannels', 1) or 1) if info else 1
            channels = min(2, max_ch) if is_loopback else 1
            device_rate = int(round(info.get('defaultSampleRate', self.sample_rate))) if info else int(self.sample_rate)
            
            # 依次尝试，参数不被支持就换下一组（PortAudio 对格式/采样率很挑）
            candidate_params = []
            for rate in (device_rate, int(self.sample_rate)):
                for fmt in (pyaudio.paFloat32, pyaudio.paInt16):
                    for ch in (channels, 1):
                        candidate_params.append((fmt, ch, rate))
            seen, attempts = set(), []
            for params in candidate_params:
                if params in seen:
                    continue
                seen.add(params)
                attempts.append(params)
            
            last_err = None
            for fmt, ch, rate in attempts:
                try:
                    stream = self.audio.open(
                        format=fmt,
                        channels=ch,
                        rate=rate,
                        input=True,
                        input_device_index=device_index,
                        frames_per_buffer=self.chunk_size,
                        stream_callback=self._audio_callback if callback is None else callback
                    )
                except Exception as e:
                    last_err = e
                    continue
                
                self.stream = stream
                self.capture_format = fmt
                self.capture_channels = ch
                self.capture_is_loopback = is_loopback
                self.device_index = device_index
                if rate != self.sample_rate:
                    self._rebuild_filters(rate)
                try:
                    self.stream.start_stream()
                except Exception:
                    pass
                self.is_recording = True
                kind = "系统音频(WASAPI环回)" if is_loopback else "输入设备"
                print(f"✓ 开始采集 [{kind}] {info.get('name') if info else device_index}: "
                      f"{ch}ch @ {rate}Hz {'float32' if fmt == pyaudio.paFloat32 else 'int16'}")
                return True
            
            self.last_error = str(last_err)
            print(f"启动音频录制失败（已尝试 {len(attempts)} 组参数）: {last_err}")
            return False
            
        except Exception as e:
            self.last_error = str(e)
            print(f"启动音频录制失败: {e}")
            return False
    
    def stop_recording(self):
        """停止音频录制"""
        if not self.is_recording:
            return
        
        self.is_recording = False
        
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        
        if self.audio:
            self.audio.terminate()
            self.audio = None
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """音频回调函数（处理 int16→float32、多声道混成单声道）"""
        if status:
            print(f"音频状态: {status}")
        
        try:
            if self.capture_format == pyaudio.paInt16:
                audio_data = np.frombuffer(in_data, dtype=np.int16).astype(np.float32) / 32768.0
            else:
                audio_data = np.frombuffer(in_data, dtype=np.float32)
            
            # WASAPI 环回一般是双声道交错数据，取平均降成单声道
            if self.capture_channels > 1:
                usable = (len(audio_data) // self.capture_channels) * self.capture_channels
                if usable > 0:
                    audio_data = audio_data[:usable].reshape(-1, self.capture_channels).mean(axis=1)
            
            if not self.audio_queue.full():
                self.audio_queue.put(audio_data)
        except Exception as e:
            print(f"音频回调错误: {e}")
        
        return (in_data, pyaudio.paContinue)
    
    def get_latest_audio_data(self, timeout=0.1):
        """获取最新的音频数据"""
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def analyze_frequency_spectrum(self, audio_data):
        """分析音频数据的频谱"""
        # 应用窗口函数
        windowed_data = audio_data * self.window[:len(audio_data)]
        
        # FFT变换
        fft_data = fft(windowed_data)
        magnitude = np.abs(fft_data[:len(fft_data)//2])  # 只取正频率部分
        
        # 频率轴
        freqs = np.fft.fftfreq(len(windowed_data), 1/self.sample_rate)[:len(magnitude)]
        
        return freqs, magnitude
    
    def separate_frequency_bands(self, audio_data):
        """分离低频和高频信号"""
        # 使用高质量滤波
        # 应用低通滤波器获得低频信号
        low_freq_signal = signal.filtfilt(
            self.lowpass_filter[0], 
            self.lowpass_filter[1], 
            audio_data
        )
        
        # 应用高通滤波器获得高频信号
        high_freq_signal = signal.filtfilt(
            self.highpass_filter[0], 
            self.highpass_filter[1], 
            audio_data
        )
        
        return low_freq_signal, high_freq_signal
    
    
    def analyze_frequency_bands(self, audio_data):
        """分析多个频段的音频能量"""
        band_analysis = {}
        
        for band_name, filter_coeffs in self.band_filters.items():
            try:
                # 应用带通滤波器
                # 使用高质量滤波
                band_signal = signal.filtfilt(filter_coeffs[0], filter_coeffs[1], audio_data)
                
                # 计算该频段的RMS能量
                rms_energy = np.sqrt(np.mean(band_signal**2))
                peak_energy = np.max(np.abs(band_signal))
                
                # 计算频谱特征
                spectral_centroid = self._calculate_spectral_centroid(band_signal)
                spectral_rolloff = self._calculate_spectral_rolloff(band_signal)
                
                band_analysis[band_name] = {
                    'rms_energy': rms_energy,
                    'peak_energy': peak_energy,
                    'spectral_centroid': spectral_centroid,
                    'spectral_rolloff': spectral_rolloff,
                    'frequency_range': self.frequency_bands[band_name]
                }
                
            except Exception as e:
                # 如果滤波失败，使用零值
                band_analysis[band_name] = {
                    'rms_energy': 0.0,
                    'peak_energy': 0.0,
                    'spectral_centroid': 0.0,
                    'spectral_rolloff': 0.0,
                    'frequency_range': self.frequency_bands[band_name]
                }
        
        return band_analysis
    
    
    def _calculate_spectral_centroid(self, audio_data):
        """计算频谱质心（音色亮度指标）"""
        if len(audio_data) < 4:
            return 0.0
            
        try:
            # FFT分析
            fft_data = np.fft.fft(audio_data)
            magnitude = np.abs(fft_data[:len(fft_data)//2])
            freqs = np.fft.fftfreq(len(audio_data), 1/self.sample_rate)[:len(magnitude)]
            
            # 计算频谱质心
            if np.sum(magnitude) > 0:
                centroid = np.sum(freqs * magnitude) / np.sum(magnitude)
                return centroid
            else:
                return 0.0
        except:
            return 0.0
    
    def _calculate_spectral_rolloff(self, audio_data):
        """计算频谱滚降点（85%能量所在的频率）"""
        if len(audio_data) < 4:
            return 0.0
            
        try:
            fft_data = np.fft.fft(audio_data)
            magnitude = np.abs(fft_data[:len(fft_data)//2])
            freqs = np.fft.fftfreq(len(audio_data), 1/self.sample_rate)[:len(magnitude)]
            
            # 计算累积能量
            total_energy = np.sum(magnitude**2)
            if total_energy == 0:
                return 0.0
                
            cumulative_energy = np.cumsum(magnitude**2)
            rolloff_idx = np.where(cumulative_energy >= 0.85 * total_energy)[0]
            
            if len(rolloff_idx) > 0:
                return freqs[rolloff_idx[0]]
            else:
                return freqs[-1]
        except:
            return 0.0
    
    def detect_audio_events(self, audio_data, previous_data=None):
        """检测音频事件特征（冲击、渐变等）"""
        events = {
            'impact_detected': False,
            'impact_intensity': 0.0,
            'frequency_shift': 0.0,
            'energy_change_rate': 0.0,
            'dominant_frequency_band': 'mid'
        }
        
        try:
            current_energy = np.mean(audio_data**2)
            
            # 检测瞬时冲击（能量突变）
            if previous_data is not None and len(previous_data) == len(audio_data):
                previous_energy = np.mean(previous_data**2)
                energy_ratio = current_energy / (previous_energy + 1e-10)
                
                # 冲击检测阈值
                if energy_ratio > 5.0:  # 能量增加5倍以上
                    events['impact_detected'] = True
                    events['impact_intensity'] = min(1.0, energy_ratio / 10.0)
                
                events['energy_change_rate'] = energy_ratio - 1.0
            
            # 分析频段分布，找出主导频段
            band_analysis = self.analyze_frequency_bands(audio_data)
            max_energy = 0.0
            dominant_band = 'mid'
            
            for band_name, analysis in band_analysis.items():
                if analysis['rms_energy'] > max_energy:
                    max_energy = analysis['rms_energy']
                    dominant_band = band_name
            
            events['dominant_frequency_band'] = dominant_band
            
            # 计算频率偏移（高频vs低频的比例）
            high_energy = (band_analysis.get('high_mid', {}).get('rms_energy', 0) + 
                          band_analysis.get('treble', {}).get('rms_energy', 0))
            low_energy = (band_analysis.get('sub_bass', {}).get('rms_energy', 0) + 
                         band_analysis.get('bass', {}).get('rms_energy', 0))
            
            if low_energy + high_energy > 1e-10:
                events['frequency_shift'] = (high_energy - low_energy) / (high_energy + low_energy)
            
        except Exception as e:
            print(f"音频事件检测错误: {e}")
        
        return events
    
    def calculate_rms_volume(self, audio_data):
        """计算RMS音量"""
        return np.sqrt(np.mean(audio_data**2))
    
    def calculate_peak_volume(self, audio_data):
        """计算峰值音量"""
        return np.max(np.abs(audio_data))
    
    def get_volume_analysis(self, audio_data):
        """获取音量分析结果"""
        rms_volume = self.calculate_rms_volume(audio_data)
        peak_volume = self.calculate_peak_volume(audio_data)
        
        # 分离频段并分析音量
        low_freq_signal, high_freq_signal = self.separate_frequency_bands(audio_data)
        
        low_freq_rms = self.calculate_rms_volume(low_freq_signal)
        high_freq_rms = self.calculate_rms_volume(high_freq_signal)
        
        # 更新音量缓冲区（用于平滑处理）
        self.volume_buffer.append({
            'total_rms': rms_volume,
            'total_peak': peak_volume,
            'low_freq_rms': low_freq_rms,
            'high_freq_rms': high_freq_rms
        })
        
        # 保持缓冲区大小
        if len(self.volume_buffer) > self.volume_window_size:
            self.volume_buffer.pop(0)
        
        # 计算平滑后的音量值
        if len(self.volume_buffer) > 0:
            avg_total_rms = np.mean([v['total_rms'] for v in self.volume_buffer])
            avg_low_rms = np.mean([v['low_freq_rms'] for v in self.volume_buffer])
            avg_high_rms = np.mean([v['high_freq_rms'] for v in self.volume_buffer])
            
            return {
                'total_rms': rms_volume,
                'total_peak': peak_volume,
                'low_freq_rms': low_freq_rms,
                'high_freq_rms': high_freq_rms,
                'smoothed_total_rms': avg_total_rms,
                'smoothed_low_rms': avg_low_rms,
                'smoothed_high_rms': avg_high_rms
            }
        
        return {
            'total_rms': rms_volume,
            'total_peak': peak_volume,
            'low_freq_rms': low_freq_rms,
            'high_freq_rms': high_freq_rms,
            'smoothed_total_rms': rms_volume,
            'smoothed_low_rms': low_freq_rms,
            'smoothed_high_rms': high_freq_rms
        }
    
    def set_filter_cutoff_frequency(self, cutoff_freq):
        """设置滤波器截止频率"""
        self.lowpass_filter = self._create_lowpass_filter(cutoff_freq)
        self.highpass_filter = self._create_highpass_filter(cutoff_freq)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频处理模块
实现实时音频采集、频谱分析和信号处理
"""

import pyaudio
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
            sample_rate: 采样率，默认44100Hz
            chunk_size: 音频块大小，默认1024（减小以降低延迟）
            device_index: 音频设备索引，None为默认设备
        """
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.device_index = device_index
        
        # 音频流相关
        self.audio = None
        self.stream = None
        self.is_recording = False
        
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
        
        # 为每个频段创建滤波器
        self.band_filters = {}
        for band_name, (low_freq, high_freq) in self.frequency_bands.items():
            self.band_filters[band_name] = self._create_bandpass_filter(low_freq, high_freq)
        
        # 保持原有的简单低通/高通滤波器用于兼容
        self.lowpass_filter = self._create_lowpass_filter(300)  
        self.highpass_filter = self._create_highpass_filter(300)
        
        # 音量分析窗口
        self.volume_buffer = []
        
        
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
        """获取可用的音频设备列表"""
        if not self.audio:
            self.audio = pyaudio.PyAudio()
        
        devices = []
        for i in range(self.audio.get_device_count()):
            device_info = self.audio.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:  # 只显示输入设备
                device_name = device_info['name']
                device_type = self._classify_device_type(device_name)
                
                devices.append({
                    'index': i,
                    'name': device_name,
                    'type': device_type,
                    'channels': device_info['maxInputChannels'],
                    'sample_rate': device_info['defaultSampleRate'],
                    'is_system_audio': device_type in ['stereo_mix', 'what_you_hear', 'loopback']
                })
        
        # 按类型排序：系统音频设备在前
        devices.sort(key=lambda x: (0 if x['is_system_audio'] else 1, x['name']))
        return devices
    
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
    
    def start_recording(self, callback=None):
        """开始音频录制"""
        if self.is_recording:
            return False
        
        try:
            if not self.audio:
                self.audio = pyaudio.PyAudio()
            
            self.stream = self.audio.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._audio_callback if callback is None else callback
            )
            
            self.stream.start_stream()
            self.is_recording = True
            return True
            
        except Exception as e:
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
        """音频回调函数"""
        if status:
            print(f"音频状态: {status}")
        
        try:
            # 将音频数据添加到队列
            audio_data = np.frombuffer(in_data, dtype=np.float32)
            # 标准模式
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

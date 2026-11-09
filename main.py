#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
声音转手柄震动控制器 - 主程序
整合音频处理、震动映射和GUI界面的完整应用程序
"""

import sys
import os
import argparse
import traceback
from pathlib import Path

# 添加当前目录到Python路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

try:
    from audio_processor import AudioProcessor
    from vibration_mapper import VibrationMapper
    from controller_manager import ControllerManager
    from audio_vibration_gui_v2 import AudioVibrationGUIv2
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保所有必需的文件都在当前目录中")
    sys.exit(1)

def check_dependencies():
    """检查必需的依赖库"""
    required_packages = {
        'XInput': 'XInput-Python',
        'pyaudio': 'pyaudio',
        'numpy': 'numpy',
        'scipy': 'scipy',
        'matplotlib': 'matplotlib',
        'tkinter': 'tkinter (通常随Python安装)'
    }
    
    missing_packages = []
    
    for package, install_name in required_packages.items():
        try:
            if package == 'tkinter':
                import tkinter
            else:
                __import__(package)
        except ImportError:
            missing_packages.append(install_name)
    
    if missing_packages:
        print("缺少以下必需的依赖库:")
        for package in missing_packages:
            print(f"  - {package}")
        print("\n请使用以下命令安装缺少的依赖:")
        print("pip install", " ".join([p for p in missing_packages if p != 'tkinter (通常随Python安装)']))
        return False
    
    return True

def setup_argument_parser():
    """设置命令行参数解析"""
    parser = argparse.ArgumentParser(
        description="声音转手柄震动控制器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用说明:
  1. 连接Xbox兼容手柄到电脑
  2. 确保音频输入设备正常工作
  3. 运行程序并在GUI中配置参数
  4. 点击"开始转换"开始实时转换

支持的手柄:
  - Xbox 360 手柄
  - Xbox One 手柄
  - Xbox Series X/S 手柄
  - 其他XInput兼容手柄

注意事项:
  - 程序需要管理员权限来访问某些音频设备
  - 确保手柄驱动程序已正确安装
  - 建议在安静环境中使用以获得最佳效果
        """)
    
    parser.add_argument('--no-gui', action='store_true',
                       help='不启动GUI界面（命令行模式）')
    
    parser.add_argument('--config', type=str, default='audio_vibration_config.json',
                       help='配置文件路径（默认: audio_vibration_config.json）')
    
    parser.add_argument('--sample-rate', type=int, default=44100,
                       help='音频采样率（默认: 44100）')
    
    parser.add_argument('--chunk-size', type=int, default=16,
                       help='音频块大小（默认: 16）')
    
    
    parser.add_argument('--no-high-priority', action='store_true',
                       help='禁用高进程优先级')
    
    parser.add_argument('--device-id', type=int, default=None,
                       help='音频设备ID（默认: 自动检测）')
    
    
    parser.add_argument('--test-audio', action='store_true',
                       help='测试音频输入设备')
    
    parser.add_argument('--test-controller', action='store_true',
                       help='测试手柄震动功能')
    
    parser.add_argument('--list-devices', action='store_true',
                       help='列出可用的音频输入设备')
    
    parser.add_argument('--setup-system-audio', action='store_true',
                       help='打开系统音频设置助手')
    
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='详细输出模式')
    
    return parser

def list_audio_devices():
    """列出音频设备"""
    print("检测音频输入设备...")
    try:
        audio_processor = AudioProcessor()
        devices = audio_processor.get_audio_devices()
        
        if not devices:
            print("未检测到可用的音频输入设备")
            return
        
        system_audio_count = sum(1 for d in devices if d['is_system_audio'])
        print(f"\n发现 {len(devices)} 个音频输入设备 (其中 {system_audio_count} 个系统音频设备):\n")
        
        for device in devices:
            device_type = ""
            if device['is_system_audio']:
                device_type = " [系统音频] ⭐"
            elif device['type'] == 'microphone':
                device_type = " [麦克风]"
            else:
                device_type = " [输入设备]"
                
            print(f"设备ID {device['index']:2d}: {device['name']}{device_type}")
            print(f"           类型: {device['type']}")
            print(f"           通道数: {device['channels']}")
            print(f"           采样率: {device['sample_rate']:.0f} Hz")
            print()
        
        if system_audio_count == 0:
            print("⚠️  未发现系统音频设备！")
            print("要捕获系统播放的音频，请：")
            print("1. 运行 'python main.py --setup-system-audio' 获取设置帮助")
            print("2. 启用Windows立体声混音功能")
            print("3. 或安装VB-Cable等虚拟音频设备")
            
    except Exception as e:
        print(f"获取音频设备失败: {e}")

def setup_system_audio():
    """系统音频设置助手"""
    try:
        from system_audio_setup import SystemAudioHelper
        helper = SystemAudioHelper()
        
        if not helper.is_windows:
            print("错误：系统音频设置助手仅支持Windows系统")
            return False
        
        # 显示设置说明
        print("="*60)
        print("系统音频设置助手")
        print("="*60)
        
        instructions = helper.get_setup_instructions()
        for instruction in instructions:
            print(instruction)
        
        # 询问是否打开设置
        while True:
            choice = input("\n是否现在打开Windows声音设置? (y/n): ").lower().strip()
            if choice in ['y', 'yes', '是']:
                success, message = helper.open_sound_settings()
                print(f"结果: {message}")
                if success:
                    print("请启用立体声混音后重新运行程序")
                break
            elif choice in ['n', 'no', '否']:
                print("请手动按照上述说明进行设置")
                break
            else:
                print("请输入 y 或 n")
        
        return True
        
    except ImportError:
        print("错误：无法导入系统音频设置助手")
        print("请确保 system_audio_setup.py 文件存在")
        return False
    except Exception as e:
        print(f"系统音频设置助手运行失败: {e}")
        return False

def test_audio_input(sample_rate=44100, chunk_size=4096, device_id=None, duration=5):
    """测试音频输入"""
    print(f"测试音频输入 (持续 {duration} 秒)...")
    try:
        audio_processor = AudioProcessor(sample_rate, chunk_size, device_id)
        
        if not audio_processor.start_recording():
            print("无法启动音频录制")
            return False
        
        print("开始录制音频，请发出声音...")
        import time
        
        start_time = time.time()
        sample_count = 0
        max_volume = 0
        
        while time.time() - start_time < duration:
            audio_data = audio_processor.get_latest_audio_data(timeout=0.5)
            if audio_data is not None:
                sample_count += 1
                volume_analysis = audio_processor.get_volume_analysis(audio_data)
                
                current_volume = volume_analysis['total_rms']
                max_volume = max(max_volume, current_volume)
                
                # 实时显示音量
                volume_bar = '█' * int(current_volume * 50)
                print(f"\r音量: {volume_bar:<50} {current_volume:.3f}", end='', flush=True)
            
            time.sleep(0.05)
        
        print(f"\n\n音频测试完成:")
        print(f"  采样数量: {sample_count}")
        print(f"  最大音量: {max_volume:.3f}")
        print(f"  音频输入: {'正常' if max_volume > 0.01 else '可能有问题（音量过低）'}")
        
        audio_processor.stop_recording()
        return True
        
    except Exception as e:
        print(f"音频测试失败: {e}")
        return False

def test_controller_vibration():
    """测试手柄震动功能"""
    print("测试手柄震动功能...")
    try:
        controller_manager = ControllerManager()
        
        if not controller_manager.connected_controllers:
            print("未检测到可用的手柄")
            return False
        
        if not controller_manager.vibration_supported:
            print("手柄不支持震动功能")
            return False
        
        print("执行震动测试...")
        controller_manager.test_vibration_pattern('basic')
        print("震动测试完成")
        
        controller_manager.cleanup()
        return True
        
    except Exception as e:
        print(f"手柄测试失败: {e}")
        return False

def set_high_priority():
    """设置高进程优先级"""
    try:
        import psutil
        import os
        
        # 获取当前进程
        current_process = psutil.Process(os.getpid())
        
        # 设置高优先级
        if os.name == 'nt':  # Windows
            current_process.nice(psutil.HIGH_PRIORITY_CLASS)
        else:  # Linux/Mac
            current_process.nice(-10)
        
        print("✓ 已设置高进程优先级")
        return True
    except ImportError:
        print("⚠️ 需要安装psutil包来设置进程优先级: pip install psutil")
        return False
    except Exception as e:
        print(f"⚠️ 设置进程优先级失败: {e}")
        return False

def run_command_line_mode(args):
    """运行命令行模式"""
    print("启动命令行模式...")
    
    # 设置优先级 (默认启用，除非用户禁用)
    if not args.no_high_priority:
        set_high_priority()
    
    
    print("按 Ctrl+C 停止程序")
    
    try:
        # 初始化组件
        audio_processor = AudioProcessor(
            sample_rate=args.sample_rate,
            chunk_size=args.chunk_size,
            device_index=args.device_id,
        )
        
        controller_manager = ControllerManager()
        if not controller_manager.connected_controllers:
            print("错误: 未检测到手柄")
            return False
        
        vibration_mapper = VibrationMapper(controller_manager)
        
        # 启动音频录制
        if not audio_processor.start_recording():
            print("错误: 无法启动音频录制")
            return False
        
        print("音频转换已启动")
        print("实时状态显示:")
        
        import time
        while True:
            try:
                audio_data = audio_processor.get_latest_audio_data(timeout=0.1)
                if audio_data is not None:
                    volume_analysis = audio_processor.get_volume_analysis(audio_data)
                    vibration_status = vibration_mapper.process_audio_frame(volume_analysis)
                    
                    # 显示状态
                    low_freq = volume_analysis.get('smoothed_low_rms', 0)
                    high_freq = volume_analysis.get('smoothed_high_rms', 0)
                    left_intensity = vibration_status['left_intensity']
                    right_intensity = vibration_status['right_intensity']
                    
                    if args.verbose:
                        print(f"\r低频: {low_freq:.3f} | 高频: {high_freq:.3f} | "
                             f"左马达: {left_intensity:.3f} | 右马达: {right_intensity:.3f}",
                             end='', flush=True)
                    else:
                        # 简化显示
                        low_bar = '█' * int(low_freq * 20)
                        high_bar = '█' * int(high_freq * 20)
                        left_bar = '█' * int(left_intensity * 20)
                        right_bar = '█' * int(right_intensity * 20)
                        
                        print(f"\r低频: {low_bar:<20} | 高频: {high_bar:<20} | "
                             f"左: {left_bar:<20} | 右: {right_bar:<20}",
                             end='', flush=True)
                
                time.sleep(0.05)
                
            except KeyboardInterrupt:
                print("\n\n程序被用户中断")
                break
            except Exception as e:
                print(f"\n处理错误: {e}")
                time.sleep(1)
        
    except Exception as e:
        print(f"命令行模式运行失败: {e}")
        return False
    
    finally:
        # 清理资源
        try:
            if 'audio_processor' in locals():
                audio_processor.stop_recording()
            if 'vibration_mapper' in locals():
                vibration_mapper.stop_vibration()
            if 'controller_manager' in locals():
                controller_manager.cleanup()
        except:
            pass
    
    return True

def run_gui_mode(args):
    """运行GUI模式"""
    print("启动图形界面模式...")
    
    # 设置优先级 (默认启用，除非用户禁用)
    if not args.no_high_priority:
        set_high_priority()
    
    
    try:
        # 初始化组件
        audio_processor = AudioProcessor(
            sample_rate=args.sample_rate,
            chunk_size=args.chunk_size,
            device_index=args.device_id,
        )
        
        controller_manager = ControllerManager()
        if not controller_manager.connected_controllers:
            print("警告: 未检测到手柄，某些功能将无法使用")
        
        vibration_mapper = VibrationMapper(controller_manager)
        
        # 创建并运行GUI v2.0
        from audio_vibration_gui_v2 import AudioVibrationGUIv2
        gui = AudioVibrationGUIv2(audio_processor, vibration_mapper, controller_manager)
        gui.config_file = args.config
        gui.run()
        
        return True
        
    except Exception as e:
        print(f"GUI模式运行失败: {e}")
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("="*60)
    print("声音转手柄震动控制器 v1.0")
    print("="*60)
    print("功能特点:")
    print("- 实时音频频谱分析")
    print("- 智能低频/高频分离")
    print("- 可配置的震动映射参数")
    print("- 多种预设模式")
    print("- 直观的GUI界面")
    print("- 支持XInput兼容手柄")
    print("="*60)
    
    # 解析命令行参数
    parser = setup_argument_parser()
    args = parser.parse_args()
    
    # 检查依赖
    if not check_dependencies():
        return 1
    
    # 处理特殊操作
    if args.list_devices:
        list_audio_devices()
        return 0
    
    if args.setup_system_audio:
        success = setup_system_audio()
        return 0 if success else 1
    
    if args.test_audio:
        success = test_audio_input(
            sample_rate=args.sample_rate,
            chunk_size=args.chunk_size,
            device_id=args.device_id
        )
        return 0 if success else 1
    
    if args.test_controller:
        success = test_controller_vibration()
        return 0 if success else 1
    
    # 运行主程序
    try:
        if args.no_gui:
            success = run_command_line_mode(args)
        else:
            success = run_gui_mode(args)
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        return 0
    except Exception as e:
        print(f"程序运行失败: {e}")
        if args.verbose:
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

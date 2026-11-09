#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
控制器管理模块
基于原有的XInput测试代码，扩展为支持实时震动控制
"""

import time
import sys
import threading
from threading import Lock

try:
    import XInput
except ImportError:
    print("错误：XInput-Python库未安装")
    print("请运行：pip install XInput-Python")
    sys.exit(1)

class ControllerManager:
    def __init__(self):
        """初始化控制器管理器"""
        self.connected_controllers = []
        self.current_controller_id = None
        self.vibration_supported = False
        self.vibration_lock = Lock()
        
        # 震动状态跟踪
        self.current_left_motor = 0
        self.current_right_motor = 0
        self.last_vibration_time = time.time()
        
        # 安全参数
        self.max_continuous_vibration_time = 30  # 最大连续震动时间（秒）
        self.vibration_start_time = None
        
        print("初始化XInput控制器管理器...")
        self.scan_controllers()
    
    def scan_controllers(self):
        """扫描可用的控制器"""
        self.connected_controllers = []
        
        for i in range(4):  # XInput最多支持4个控制器
            try:
                state = XInput.get_state(i)
                self.connected_controllers.append(i)
                print(f"检测到控制器 {i}")
            except:
                continue
        
        if not self.connected_controllers:
            print("未检测到XInput兼容的控制器")
            print("请确保：")
            print("1. 手柄已正确连接")
            print("2. 手柄为Xbox系列或XInput兼容手柄")
            print("3. 手柄驱动已正确安装")
            return False
        
        # 使用第一个连接的控制器
        self.current_controller_id = self.connected_controllers[0]
        print(f"使用控制器 {self.current_controller_id}")
        
        # 测试震动功能
        self.test_vibration_support()
        return True
    
    def test_vibration_support(self):
        """测试震动功能支持"""
        print("测试XInput震动功能...")
        try:
            # 短暂测试震动
            XInput.set_vibration(self.current_controller_id, 16384, 16384)  # 25% 强度
            time.sleep(0.1)
            XInput.set_vibration(self.current_controller_id, 0, 0)  # 停止震动
            print("✓ XInput震动功能正常")
            self.vibration_supported = True
        except Exception as e:
            print(f"❌ XInput震动功能测试失败: {e}")
            self.vibration_supported = False
    
    def get_controller_info(self):
        """获取控制器信息"""
        if not self.connected_controllers:
            return None
        
        info = {
            'controller_count': len(self.connected_controllers),
            'current_controller': self.current_controller_id,
            'vibration_supported': self.vibration_supported,
            'connected_controllers': self.connected_controllers
        }
        
        # 获取当前控制器详细状态
        if self.current_controller_id is not None:
            try:
                state = XInput.get_state(self.current_controller_id)
                buttons = XInput.get_button_values(state)
                triggers = XInput.get_trigger_values(state)
                thumbs = XInput.get_thumb_values(state)
                
                info.update({
                    'packet_number': state.dwPacketNumber,
                    'buttons': buttons,
                    'triggers': triggers,
                    'thumbs': thumbs
                })
            except Exception as e:
                info['error'] = str(e)
        
        return info
    
    def set_controller(self, controller_id):
        """设置使用的控制器"""
        if controller_id in self.connected_controllers:
            self.current_controller_id = controller_id
            print(f"切换到控制器 {controller_id}")
            return True
        return False
    
    def refresh_controllers(self):
        """刷新控制器连接状态"""
        print("正在刷新控制器连接...")
        old_count = len(self.connected_controllers)
        
        # 重新扫描控制器
        result = self.scan_controllers()
        
        new_count = len(self.connected_controllers)
        if new_count != old_count:
            print(f"控制器数量变化: {old_count} -> {new_count}")
        
        return result
    
    def set_vibration(self, left_motor, right_motor, force=False):
        """
        设置震动强度
        
        Args:
            left_motor: 左马达强度 (0-65535)
            right_motor: 右马达强度 (0-65535)
            force: 强制发送震动，忽略连接检查
        """
        # 如果不是强制模式，进行正常检查
        if not force and (not self.vibration_supported or self.current_controller_id is None):
            return False
        
        # 安全检查：限制震动值范围
        left_motor = max(0, min(65535, int(left_motor)))
        right_motor = max(0, min(65535, int(right_motor)))
        
        # 检查连续震动时间限制
        if left_motor > 0 or right_motor > 0:
            current_time = time.time()
            if self.vibration_start_time is None:
                self.vibration_start_time = current_time
            elif current_time - self.vibration_start_time > self.max_continuous_vibration_time:
                print("警告：达到最大连续震动时间限制，强制停止震动")
                left_motor = right_motor = 0
                self.vibration_start_time = None
        else:
            self.vibration_start_time = None
        
        try:
            with self.vibration_lock:
                # 强制模式时，尝试发送到所有可能的控制器
                if force:
                    success_count = 0
                    for controller_id in range(4):  # XInput支持0-3
                        try:
                            XInput.set_vibration(controller_id, left_motor, right_motor)
                            success_count += 1
                        except:
                            continue
                    
                    if success_count > 0:
                        self.current_left_motor = left_motor
                        self.current_right_motor = right_motor
                        self.last_vibration_time = time.time()
                        print(f"强制震动发送成功 (影响 {success_count} 个控制器)")
                        return True
                    else:
                        print("强制震动发送失败：没有可用的控制器")
                        return False
                else:
                    # 正常模式
                    XInput.set_vibration(self.current_controller_id, left_motor, right_motor)
                    self.current_left_motor = left_motor
                    self.current_right_motor = right_motor
                    self.last_vibration_time = time.time()
                    return True
            
        except Exception as e:
            print(f"设置震动失败: {e}")
            return False
    
    def stop_vibration(self, force=False):
        """停止所有震动"""
        return self.set_vibration(0, 0, force=force)
    
    def get_vibration_status(self):
        """获取当前震动状态"""
        with self.vibration_lock:
            return {
                'left_motor': self.current_left_motor,
                'right_motor': self.current_right_motor,
                'left_intensity': self.current_left_motor / 65535.0,
                'right_intensity': self.current_right_motor / 65535.0,
                'last_update': self.last_vibration_time,
                'is_vibrating': self.current_left_motor > 0 or self.current_right_motor > 0
            }
    
    def force_vibration_test(self, pattern='basic'):
        """强制震动测试（忽略连接状态）"""
        print(f"开始强制震动测试: {pattern}")
        
        try:
            if pattern == 'basic':
                # 基础测试：左-右-双侧
                self.set_vibration(32768, 0, force=True)  # 左侧50%
                time.sleep(0.5)
                self.set_vibration(0, 32768, force=True)  # 右侧50%
                time.sleep(0.5)
                self.set_vibration(32768, 32768, force=True)  # 双侧50%
                time.sleep(0.5)
                self.set_vibration(0, 0, force=True)  # 停止
                
            elif pattern == 'pulse':
                # 脉冲模式
                for i in range(5):
                    intensity = int((i + 1) * 13107)  # 递增强度
                    self.set_vibration(intensity, intensity, force=True)
                    time.sleep(0.2)
                    self.set_vibration(0, 0, force=True)
                    time.sleep(0.1)
                    
            elif pattern == 'wave':
                # 波浪模式
                for i in range(20):
                    intensity = int(32768 * (0.5 + 0.5 * abs(i % 10 - 5) / 5))
                    left_intensity = intensity if i % 2 == 0 else 0
                    right_intensity = intensity if i % 2 == 1 else 0
                    self.set_vibration(left_intensity, right_intensity, force=True)
                    time.sleep(0.1)
                
                self.set_vibration(0, 0, force=True)
                
            print("强制震动测试完成")
            
        except Exception as e:
            print(f"强制震动测试失败: {e}")
            self.set_vibration(0, 0, force=True)
    
    def test_vibration_pattern(self, pattern='basic'):
        """测试震动模式"""
        if not self.vibration_supported:
            print("震动功能不支持，尝试强制模式...")
            self.force_vibration_test(pattern)
            return
        
        print(f"开始测试震动模式: {pattern}")
        
        try:
            if pattern == 'basic':
                # 基础测试：左-右-双侧
                self.set_vibration(32768, 0)  # 左侧50%
                time.sleep(0.5)
                self.set_vibration(0, 32768)  # 右侧50%
                time.sleep(0.5)
                self.set_vibration(32768, 32768)  # 双侧50%
                time.sleep(0.5)
                self.stop_vibration()
                
            elif pattern == 'pulse':
                # 脉冲模式
                for i in range(5):
                    intensity = int((i + 1) * 13107)  # 递增强度
                    self.set_vibration(intensity, intensity)
                    time.sleep(0.2)
                    self.stop_vibration()
                    time.sleep(0.1)
                    
            elif pattern == 'wave':
                # 波浪模式
                for i in range(20):
                    intensity = int(32768 * (0.5 + 0.5 * abs(i % 10 - 5) / 5))
                    left_intensity = intensity if i % 2 == 0 else 0
                    right_intensity = intensity if i % 2 == 1 else 0
                    self.set_vibration(left_intensity, right_intensity)
                    time.sleep(0.1)
                
                self.stop_vibration()
                
            print("震动模式测试完成")
            
        except Exception as e:
            print(f"震动模式测试失败: {e}")
            self.stop_vibration()
    
    def emergency_stop(self):
        """紧急停止所有震动"""
        print("执行紧急停止...")
        try:
            for controller_id in self.connected_controllers:
                XInput.set_vibration(controller_id, 0, 0)
            
            with self.vibration_lock:
                self.current_left_motor = 0
                self.current_right_motor = 0
                self.vibration_start_time = None
            
            print("紧急停止完成")
            return True
            
        except Exception as e:
            print(f"紧急停止失败: {e}")
            return False
    
    def cleanup(self):
        """清理资源"""
        print("清理控制器资源...")
        self.emergency_stop()
        # XInput库不需要显式关闭连接
        print("控制器资源清理完成")
    
    def __del__(self):
        """析构函数"""
        self.cleanup()

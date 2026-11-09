#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频转震动GUI界面 - 重新设计版本
支持智能声音识别和差异化震动功能
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib
import threading
import time
import json
import queue
import platform
import os
import glob

class AudioVibrationGUIv2:
    def __init__(self, audio_processor, vibration_mapper, controller_manager):
        """
        初始化GUI界面
        """
        self.audio_processor = audio_processor
        self.vibration_mapper = vibration_mapper
        self.controller_manager = controller_manager
        
        # GUI状态
        self.is_running = False
        self.processing_thread = None
        self.monitoring_thread = None
        
        # 数据缓冲区
        self.max_buffer_size = 200
        self.audio_data_buffer = []
        self.vibration_data_buffer = []
        self.sound_type_history = []
        
        # FPS计算
        self.fps = 0
        self.fps_times = []
        
        # 配置文件
        self.config_file = "audio_vibration_config.json"
        
        # 创建主窗口
        self.setup_main_window()
        
        # 设置中文字体
        self.setup_fonts()
        
        # 创建GUI组件
        self.setup_gui_components()
        
        # 启动监控线程
        self.start_monitoring()
        
        # 刷新配置列表
        self.refresh_config_list()
        
        # 初始化手柄状态显示
        self.root.after(500, self.update_controller_status)  # 延迟500ms后更新
    
    def setup_main_window(self):
        """设置主窗口"""
        self.root = tk.Tk()
        self.root.title("🎯 智能音频转震动系统 v2.0")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)
        
        # 设置样式
        style = ttk.Style()
        style.theme_use('clam')
        
        # 配置颜色
        style.configure('Title.TLabel', font=('Arial', 12, 'bold'))
        style.configure('Status.TLabel', font=('Consolas', 10))
        style.configure('Data.TLabel', font=('Consolas', 9, 'bold'))
    
    def setup_fonts(self):
        """设置中文字体支持"""
        try:
            system = platform.system()
            
            if system == "Windows":
                # Windows系统中文字体
                chinese_fonts = ['Microsoft YaHei', 'SimHei', 'SimSun', 'KaiTi']
            elif system == "Darwin":  # macOS
                chinese_fonts = ['PingFang SC', 'Hei', 'STSong', 'STKaiti']
            else:  # Linux
                chinese_fonts = ['Noto Sans CJK SC', 'WenQuanYi Micro Hei', 'DejaVu Sans']
            
            # 尝试设置中文字体
            font_set = False
            for font in chinese_fonts:
                try:
                    matplotlib.rcParams['font.sans-serif'] = [font] + matplotlib.rcParams['font.sans-serif']
                    matplotlib.rcParams['axes.unicode_minus'] = False  # 正确显示负号
                    
                    # 测试字体是否可用
                    import matplotlib.font_manager as fm
                    if any(font in f.name for f in fm.fontManager.ttflist):
                        print(f"✓ 设置中文字体: {font}")
                        font_set = True
                        break
                except Exception as e:
                    continue
            
            if not font_set:
                print("⚠️ 警告: 未找到合适的中文字体，图表中的中文可能显示为方框")
                print("建议安装字体: Microsoft YaHei (Windows) 或 Noto Sans CJK SC (Linux)")
        
        except Exception as e:
            print(f"字体设置出错: {e}")
            # 回退到默认设置
            matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'sans-serif']
    
    def setup_gui_components(self):
        """设置GUI组件"""
        # 创建主容器
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 创建左右分栏
        left_frame = ttk.Frame(main_container)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        right_frame = ttk.Frame(main_container)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(5, 0))
        
        # 左侧：控制面板
        self.setup_control_panels(left_frame)
        
        # 右侧：监控面板
        self.setup_monitoring_panel(right_frame)
        
        # 底部：状态栏
        self.setup_status_bar()
    
    def setup_control_panels(self, parent):
        """设置控制面板"""
        # 创建选项卡控件
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # 选项卡1：基础设置
        basic_frame = ttk.Frame(notebook)
        notebook.add(basic_frame, text="🎚️ 基础设置")
        self.setup_basic_panel(basic_frame)
        
        # 选项卡2：声音识别
        classification_frame = ttk.Frame(notebook)
        notebook.add(classification_frame, text="🎯 声音识别")
        self.setup_classification_panel(classification_frame)
        
        # 选项卡3：冲击增强
        impact_frame = ttk.Frame(notebook)
        notebook.add(impact_frame, text="💥 冲击增强")
        self.setup_impact_panel(impact_frame)
        
        # 选项卡4：高级设置
        advanced_frame = ttk.Frame(notebook)
        notebook.add(advanced_frame, text="⚙️ 高级设置")
        self.setup_advanced_panel(advanced_frame)
    
    def setup_basic_panel(self, parent):
        """设置基础面板"""
        # 设备选择
        device_group = ttk.LabelFrame(parent, text="🎧 音频设备")
        device_group.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(device_group, text="输入设备:").pack(anchor=tk.W, padx=5, pady=2)
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(device_group, textvariable=self.device_var, state="readonly")
        self.device_combo.pack(fill=tk.X, padx=5, pady=2)
        self.device_combo.bind('<<ComboboxSelected>>', self.on_device_changed)
        
        device_buttons = ttk.Frame(device_group)
        device_buttons.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(device_buttons, text="刷新设备", command=self.refresh_devices).pack(side=tk.LEFT)
        
        # 手柄控制
        controller_group = ttk.LabelFrame(parent, text="🎮 手柄控制")
        controller_group.pack(fill=tk.X, padx=5, pady=5)
        
        # 手柄状态显示
        controller_status_frame = ttk.Frame(controller_group)
        controller_status_frame.pack(fill=tk.X, padx=5, pady=(5, 2))
        
        ttk.Label(controller_status_frame, text="手柄状态:").pack(side=tk.LEFT)
        self.controller_status_label = ttk.Label(controller_status_frame, text="检查中...", foreground='orange')
        self.controller_status_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # 手柄控制按钮
        controller_buttons = ttk.Frame(controller_group)
        controller_buttons.pack(fill=tk.X, padx=5, pady=(2, 5))
        
        ttk.Button(controller_buttons, text="🔄 刷新手柄", command=self.refresh_controllers).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(controller_buttons, text="💪 强制震动测试", command=self.force_vibration_test).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(controller_buttons, text="⏹️ 强制停止", command=self.force_stop_vibration).pack(side=tk.LEFT)
        
        # 基础参数
        params_group = ttk.LabelFrame(parent, text="🎛️ 基础参数")
        params_group.pack(fill=tk.X, padx=5, pady=5)
        
        # 敏感度设置
        sens_frame = ttk.Frame(params_group)
        sens_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(sens_frame, text="低频敏感度:").grid(row=0, column=0, sticky=tk.W)
        self.low_sens_var = tk.DoubleVar(value=1.0)
        self.low_sens_scale = ttk.Scale(sens_frame, from_=0.1, to=3.0, variable=self.low_sens_var, 
                                       orient=tk.HORIZONTAL, command=self.update_sensitivity)
        self.low_sens_scale.grid(row=0, column=1, sticky=tk.EW, padx=5)
        self.low_sens_label = ttk.Label(sens_frame, text="1.00")
        self.low_sens_label.grid(row=0, column=2)
        
        ttk.Label(sens_frame, text="高频敏感度:").grid(row=1, column=0, sticky=tk.W)
        self.high_sens_var = tk.DoubleVar(value=2.5)
        self.high_sens_scale = ttk.Scale(sens_frame, from_=0.1, to=3.0, variable=self.high_sens_var, 
                                        orient=tk.HORIZONTAL, command=self.update_sensitivity)
        self.high_sens_scale.grid(row=1, column=1, sticky=tk.EW, padx=5)
        self.high_sens_label = ttk.Label(sens_frame, text="1.00")
        self.high_sens_label.grid(row=1, column=2)
        
        ttk.Label(sens_frame, text="整体强度:").grid(row=2, column=0, sticky=tk.W)
        self.overall_var = tk.DoubleVar(value=1.0)
        self.overall_scale = ttk.Scale(sens_frame, from_=0.0, to=2.0, variable=self.overall_var, 
                                      orient=tk.HORIZONTAL, command=self.update_sensitivity)
        self.overall_scale.grid(row=2, column=1, sticky=tk.EW, padx=5)
        self.overall_label = ttk.Label(sens_frame, text="1.00")
        self.overall_label.grid(row=2, column=2)
        
        sens_frame.columnconfigure(1, weight=1)
        
        # 响应阈值设置
        threshold_group = ttk.LabelFrame(parent, text="🚪 响应阈值")
        threshold_group.pack(fill=tk.X, padx=5, pady=5)
        
        threshold_frame = ttk.Frame(threshold_group)
        threshold_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(threshold_frame, text="低频阈值:").grid(row=0, column=0, sticky=tk.W)
        self.low_threshold_var = tk.DoubleVar(value=0.15)
        self.low_threshold_scale = ttk.Scale(threshold_frame, from_=0.001, to=1.0, variable=self.low_threshold_var, 
                                           orient=tk.HORIZONTAL, command=self.update_thresholds_basic)
        self.low_threshold_scale.grid(row=0, column=1, sticky=tk.EW, padx=5)
        self.low_threshold_label = ttk.Label(threshold_frame, text="0.010")
        self.low_threshold_label.grid(row=0, column=2)
        
        ttk.Label(threshold_frame, text="高频阈值:").grid(row=1, column=0, sticky=tk.W)
        self.high_threshold_var = tk.DoubleVar(value=0.05)
        self.high_threshold_scale = ttk.Scale(threshold_frame, from_=0.001, to=1.0, variable=self.high_threshold_var, 
                                            orient=tk.HORIZONTAL, command=self.update_thresholds_basic)
        self.high_threshold_scale.grid(row=1, column=1, sticky=tk.EW, padx=5)
        self.high_threshold_label = ttk.Label(threshold_frame, text="0.010")
        self.high_threshold_label.grid(row=1, column=2)
        
        threshold_frame.columnconfigure(1, weight=1)
        
        # 通用音量范围设置
        range_frame = ttk.Frame(threshold_group)
        range_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(range_frame, text="最小音量:").grid(row=0, column=0, sticky=tk.W)
        self.min_volume_var = tk.DoubleVar(value=0.03)
        self.min_volume_scale = ttk.Scale(range_frame, from_=0.001, to=1.0, variable=self.min_volume_var, 
                                        orient=tk.HORIZONTAL, command=self.update_volume_range)
        self.min_volume_scale.grid(row=0, column=1, sticky=tk.EW, padx=5)
        self.min_volume_label = ttk.Label(range_frame, text="0.010")
        self.min_volume_label.grid(row=0, column=2)
        
        ttk.Label(range_frame, text="最大音量:").grid(row=1, column=0, sticky=tk.W)
        self.max_volume_var = tk.DoubleVar(value=1.0)
        self.max_volume_scale = ttk.Scale(range_frame, from_=0.1, to=2.0, variable=self.max_volume_var, 
                                        orient=tk.HORIZONTAL, command=self.update_volume_range)
        self.max_volume_scale.grid(row=1, column=1, sticky=tk.EW, padx=5)
        self.max_volume_label = ttk.Label(range_frame, text="1.000")
        self.max_volume_label.grid(row=1, column=2)
        
        range_frame.columnconfigure(1, weight=1)
        
        # 添加说明文本
        help_label = ttk.Label(threshold_group, text="分频阈值：过滤噪音 | 音量范围：优化动态范围映射", 
                              font=('Arial', 8), foreground='gray')
        help_label.pack(padx=5, pady=2)
        
        # 配置管理
        config_group = ttk.LabelFrame(parent, text="💾 配置管理")
        config_group.pack(fill=tk.X, padx=5, pady=5)
        
        # 加载配置选择
        load_frame = ttk.Frame(config_group)
        load_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(load_frame, text="配置:").pack(side=tk.LEFT)
        self.config_var = tk.StringVar()
        self.config_combo = ttk.Combobox(load_frame, textvariable=self.config_var, 
                                        state="readonly", width=20)
        self.config_combo.pack(side=tk.LEFT, padx=5)
        self.config_combo.bind('<<ComboboxSelected>>', self.on_config_selected)
        
        ttk.Button(load_frame, text="🔄", command=self.refresh_config_list).pack(side=tk.LEFT, padx=2)
        
        # 操作按钮
        config_buttons_frame = ttk.Frame(config_group)
        config_buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(config_buttons_frame, text="💾 保存配置", 
                  command=self.save_configuration).pack(side=tk.LEFT, padx=5)
        ttk.Button(config_buttons_frame, text="📁 加载选中", 
                  command=self.load_selected_configuration).pack(side=tk.LEFT, padx=5)
        ttk.Button(config_buttons_frame, text="🗑️ 删除配置", 
                  command=self.delete_configuration).pack(side=tk.LEFT, padx=5)
        ttk.Button(config_buttons_frame, text="🔄 重置默认", 
                  command=self.reset_to_defaults).pack(side=tk.LEFT, padx=5)
        
        # 控制按钮
        control_group = ttk.LabelFrame(parent, text="🎮 控制")
        control_group.pack(fill=tk.X, padx=5, pady=5)
        
        button_frame = ttk.Frame(control_group)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.start_button = ttk.Button(button_frame, text="开始转换", command=self.toggle_conversion)
        self.start_button.pack(side=tk.LEFT, padx=2)
        
        ttk.Button(button_frame, text="测试震动", command=self.test_vibration).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="紧急停止", command=self.emergency_stop).pack(side=tk.LEFT, padx=2)
    
    def setup_classification_panel(self, parent):
        """设置声音分类面板"""
        # 分类总开关
        switch_group = ttk.LabelFrame(parent, text="🎯 声音识别开关")
        switch_group.pack(fill=tk.X, padx=5, pady=5)
        
        self.classification_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(switch_group, text="启用智能声音识别", 
                       variable=self.classification_enabled, 
                       command=self.toggle_classification).pack(anchor=tk.W, padx=5, pady=5)
        
        # 声音类型增强设置
        enhancement_group = ttk.LabelFrame(parent, text="🔊 声音类型增强")
        enhancement_group.pack(fill=tk.X, padx=5, pady=5)
        
        # 爆炸增强
        explosion_frame = ttk.Frame(enhancement_group)
        explosion_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(explosion_frame, text="💥 爆炸增强:").pack(side=tk.LEFT, anchor=tk.W, padx=(0, 5))
        self.explosion_boost_var = tk.DoubleVar(value=2.5)
        explosion_scale = ttk.Scale(explosion_frame, from_=1.0, to=5.0, variable=self.explosion_boost_var, 
                                   orient=tk.HORIZONTAL, command=self.update_sound_boosts)
        explosion_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.explosion_boost_label = ttk.Label(explosion_frame, text="2.50")
        self.explosion_boost_label.pack(side=tk.RIGHT)
        
        # 金属增强
        metal_frame = ttk.Frame(enhancement_group)
        metal_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(metal_frame, text="⚔️ 金属增强:").pack(side=tk.LEFT, anchor=tk.W, padx=(0, 5))
        self.metal_boost_var = tk.DoubleVar(value=2.0)
        metal_scale = ttk.Scale(metal_frame, from_=1.0, to=4.0, variable=self.metal_boost_var, 
                               orient=tk.HORIZONTAL, command=self.update_sound_boosts)
        metal_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.metal_boost_label = ttk.Label(metal_frame, text="2.00")
        self.metal_boost_label.pack(side=tk.RIGHT)
        
        # 识别敏感度设置
        threshold_group = ttk.LabelFrame(parent, text="🎚️ 识别敏感度")
        threshold_group.pack(fill=tk.X, padx=5, pady=5)
        
        # 爆炸识别阈值
        exp_thresh_frame = ttk.Frame(threshold_group)
        exp_thresh_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(exp_thresh_frame, text="💥 爆炸阈值:").pack(side=tk.LEFT, anchor=tk.W, padx=(0, 5))
        self.explosion_threshold_var = tk.DoubleVar(value=0.3)
        exp_thresh_scale = ttk.Scale(exp_thresh_frame, from_=0.1, to=0.8, variable=self.explosion_threshold_var, 
                                    orient=tk.HORIZONTAL, command=self.update_thresholds)
        exp_thresh_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.explosion_threshold_label = ttk.Label(exp_thresh_frame, text="0.30")
        self.explosion_threshold_label.pack(side=tk.RIGHT)
        
        # 金属识别阈值
        metal_thresh_frame = ttk.Frame(threshold_group)
        metal_thresh_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(metal_thresh_frame, text="⚔️ 金属阈值:").pack(side=tk.LEFT, anchor=tk.W, padx=(0, 5))
        self.metal_threshold_var = tk.DoubleVar(value=0.25)
        metal_thresh_scale = ttk.Scale(metal_thresh_frame, from_=0.1, to=0.8, variable=self.metal_threshold_var, 
                                      orient=tk.HORIZONTAL, command=self.update_thresholds)
        metal_thresh_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.metal_threshold_label = ttk.Label(metal_thresh_frame, text="0.25")
        self.metal_threshold_label.pack(side=tk.RIGHT)
    
    def setup_impact_panel(self, parent):
        """设置冲击增强面板"""
        # 冲击开关
        impact_switch_group = ttk.LabelFrame(parent, text="💥 冲击增强开关")
        impact_switch_group.pack(fill=tk.X, padx=5, pady=5)
        
        self.impact_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(impact_switch_group, text="启用冲击增强", 
                       variable=self.impact_enabled, 
                       command=self.toggle_impact_enhancement).pack(anchor=tk.W, padx=5, pady=5)
        
        # 冲击参数
        impact_params_group = ttk.LabelFrame(parent, text="⚡ 冲击参数")
        impact_params_group.pack(fill=tk.X, padx=5, pady=5)
        
        # 冲击倍数
        multiplier_frame = ttk.Frame(impact_params_group)
        multiplier_frame.pack(fill=tk.X, padx=5, pady=3)
        ttk.Label(multiplier_frame, text="冲击倍数:").pack(side=tk.LEFT, anchor=tk.W, padx=(0, 5))
        self.impact_multiplier_var = tk.DoubleVar(value=3.0)
        multiplier_scale = ttk.Scale(multiplier_frame, from_=1.0, to=8.0, variable=self.impact_multiplier_var, 
                                    orient=tk.HORIZONTAL, command=self.update_impact_settings)
        multiplier_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.impact_multiplier_label = ttk.Label(multiplier_frame, text="3.00")
        self.impact_multiplier_label.pack(side=tk.RIGHT)
        
        # 冲击持续时间
        duration_frame = ttk.Frame(impact_params_group)
        duration_frame.pack(fill=tk.X, padx=5, pady=3)
        ttk.Label(duration_frame, text="持续时间(秒):").pack(side=tk.LEFT, anchor=tk.W, padx=(0, 5))
        self.impact_duration_var = tk.DoubleVar(value=0.15)
        duration_scale = ttk.Scale(duration_frame, from_=0.05, to=0.5, variable=self.impact_duration_var, 
                                  orient=tk.HORIZONTAL, command=self.update_impact_settings)
        duration_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.impact_duration_label = ttk.Label(duration_frame, text="0.15")
        self.impact_duration_label.pack(side=tk.RIGHT)
        
        # 冲击检测设置
        detection_group = ttk.LabelFrame(parent, text="🔍 冲击检测")
        detection_group.pack(fill=tk.X, padx=5, pady=5)
        
        # 能量阈值
        energy_thresh_frame = ttk.Frame(detection_group)
        energy_thresh_frame.pack(fill=tk.X, padx=5, pady=3)
        ttk.Label(energy_thresh_frame, text="能量阈值倍数:").pack(side=tk.LEFT, anchor=tk.W, padx=(0, 5))
        self.energy_threshold_var = tk.DoubleVar(value=5.0)
        energy_thresh_scale = ttk.Scale(energy_thresh_frame, from_=2.0, to=10.0, variable=self.energy_threshold_var, 
                                       orient=tk.HORIZONTAL, command=self.update_detection_settings)
        energy_thresh_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.energy_threshold_label = ttk.Label(energy_thresh_frame, text="5.00")
        self.energy_threshold_label.pack(side=tk.RIGHT)
    
    def setup_advanced_panel(self, parent):
        """设置高级面板"""
        # 平滑设置
        smoothing_group = ttk.LabelFrame(parent, text="🌊 平滑设置")
        smoothing_group.pack(fill=tk.X, padx=5, pady=5)
        
        smooth_frame = ttk.Frame(smoothing_group)
        smooth_frame.pack(fill=tk.X, padx=5, pady=3)
        ttk.Label(smooth_frame, text="平滑因子:").pack(side=tk.LEFT, anchor=tk.W, padx=(0, 5))
        self.smoothing_var = tk.DoubleVar(value=0.0)
        smoothing_scale = ttk.Scale(smooth_frame, from_=0.0, to=1.0, variable=self.smoothing_var, 
                                   orient=tk.HORIZONTAL, command=self.update_advanced_settings)
        smoothing_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.smoothing_label = ttk.Label(smooth_frame, text="0.70")
        self.smoothing_label.pack(side=tk.RIGHT)
        
        # 频率分离点
        cutoff_frame = ttk.Frame(smoothing_group)
        cutoff_frame.pack(fill=tk.X, padx=5, pady=3)
        ttk.Label(cutoff_frame, text="频率分离点(Hz):").pack(side=tk.LEFT, anchor=tk.W, padx=(0, 5))
        self.cutoff_var = tk.DoubleVar(value=400)
        cutoff_scale = ttk.Scale(cutoff_frame, from_=100, to=1000, variable=self.cutoff_var, 
                                orient=tk.HORIZONTAL, command=self.update_advanced_settings)
        cutoff_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.cutoff_label = ttk.Label(cutoff_frame, text="300")
        self.cutoff_label.pack(side=tk.RIGHT)
        
        # 频率差增强设置
        freq_diff_group = ttk.LabelFrame(parent, text="🎚️ 频率差增强")
        freq_diff_group.pack(fill=tk.X, padx=5, pady=5)
        
        freq_diff_frame = ttk.Frame(freq_diff_group)
        freq_diff_frame.pack(fill=tk.X, padx=5, pady=3)
        ttk.Label(freq_diff_frame, text="频率差:").pack(side=tk.LEFT, anchor=tk.W, padx=(0, 5))
        self.frequency_diff_var = tk.DoubleVar(value=1.0)
        freq_diff_scale = ttk.Scale(freq_diff_frame, from_=0.0, to=1.0, variable=self.frequency_diff_var, 
                                   orient=tk.HORIZONTAL, command=self.update_advanced_settings)
        freq_diff_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.frequency_diff_label = ttk.Label(freq_diff_frame, text="0.00")
        self.frequency_diff_label.pack(side=tk.RIGHT)
        
        # 添加说明文本
        help_label = ttk.Label(freq_diff_group, text="增强主导频段，弱化非主导频段 (0=无变化, 1=最大差异)", 
                              font=('Arial', 8), foreground='gray')
        help_label.pack(padx=5, pady=2)
        
        # 配置管理已移至首页基础设置，此处移除重复按钮
    
    def setup_monitoring_panel(self, parent):
        """设置监控面板"""
        # 实时数据显示
        data_group = ttk.LabelFrame(parent, text="📊 实时数据")
        data_group.pack(fill=tk.X, padx=5, pady=5)
        
        # 音频数据
        audio_data_frame = ttk.Frame(data_group)
        audio_data_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(audio_data_frame, text="低频:", style='Data.TLabel').grid(row=0, column=0, sticky=tk.W)
        self.low_freq_display = ttk.Label(audio_data_frame, text="0.000", style='Data.TLabel')
        self.low_freq_display.grid(row=0, column=1, sticky=tk.W, padx=10)
        
        ttk.Label(audio_data_frame, text="高频:", style='Data.TLabel').grid(row=0, column=2, sticky=tk.W)
        self.high_freq_display = ttk.Label(audio_data_frame, text="0.000", style='Data.TLabel')
        self.high_freq_display.grid(row=0, column=3, sticky=tk.W, padx=10)
        
        # 震动数据
        ttk.Label(audio_data_frame, text="左马达:", style='Data.TLabel').grid(row=1, column=0, sticky=tk.W)
        self.left_motor_display = ttk.Label(audio_data_frame, text="0 (0.0%)", style='Data.TLabel')
        self.left_motor_display.grid(row=1, column=1, sticky=tk.W, padx=10)
        
        ttk.Label(audio_data_frame, text="右马达:", style='Data.TLabel').grid(row=1, column=2, sticky=tk.W)
        self.right_motor_display = ttk.Label(audio_data_frame, text="0 (0.0%)", style='Data.TLabel')
        self.right_motor_display.grid(row=1, column=3, sticky=tk.W, padx=10)
        
        # 声音识别状态
        recognition_group = ttk.LabelFrame(parent, text="🎯 声音识别状态")
        recognition_group.pack(fill=tk.X, padx=5, pady=5)
        
        recognition_frame = ttk.Frame(recognition_group)
        recognition_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(recognition_frame, text="当前类型:", style='Data.TLabel').grid(row=0, column=0, sticky=tk.W)
        self.sound_type_display = ttk.Label(recognition_frame, text="🔇 静音", style='Data.TLabel')
        self.sound_type_display.grid(row=0, column=1, sticky=tk.W, padx=10)
        
        ttk.Label(recognition_frame, text="冲击状态:", style='Data.TLabel').grid(row=1, column=0, sticky=tk.W)
        self.impact_status_display = ttk.Label(recognition_frame, text="❌ 无冲击", style='Data.TLabel')
        self.impact_status_display.grid(row=1, column=1, sticky=tk.W, padx=10)
        
        # 频段分析
        bands_group = ttk.LabelFrame(parent, text="📈 频段分析")
        bands_group.pack(fill=tk.X, padx=5, pady=5)
        
        self.setup_frequency_bands_display(bands_group)
        
        # 图表
        chart_group = ttk.LabelFrame(parent, text="📉 波形图表")
        chart_group.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.setup_charts(chart_group)
    
    def setup_frequency_bands_display(self, parent):
        """设置频段显示"""
        bands_frame = ttk.Frame(parent)
        bands_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 频段标签和进度条
        self.band_displays = {}
        band_names = {
            'sub_bass': '超低频',
            'bass': '低频', 
            'low_mid': '中低频',
            'mid': '中频',
            'high_mid': '中高频',
            'treble': '高频'
        }
        
        for i, (band_key, band_name) in enumerate(band_names.items()):
            row = i // 2
            col = (i % 2) * 3
            
            ttk.Label(bands_frame, text=f"{band_name}:", style='Data.TLabel').grid(
                row=row, column=col, sticky=tk.W, padx=2, pady=2)
            
            progress = ttk.Progressbar(bands_frame, length=80, mode='determinate')
            progress.grid(row=row, column=col+1, sticky=tk.EW, padx=5, pady=2)
            
            value_label = ttk.Label(bands_frame, text="0.00", style='Data.TLabel')
            value_label.grid(row=row, column=col+2, sticky=tk.W, padx=2, pady=2)
            
            self.band_displays[band_key] = {
                'progress': progress,
                'label': value_label
            }
        
        bands_frame.columnconfigure(1, weight=1)
        bands_frame.columnconfigure(4, weight=1)
    
    def setup_charts(self, parent):
        """设置图表"""
        # 创建matplotlib图表
        self.figure = Figure(figsize=(6, 4), dpi=80)
        self.figure.patch.set_facecolor('white')
        
        # 音频波形图
        self.audio_ax = self.figure.add_subplot(211)
        self.audio_ax.set_title('音频频谱', fontsize=10)
        self.audio_ax.set_ylabel('幅度', fontsize=8)
        self.audio_ax.grid(True, alpha=0.3)
        
        # 震动强度图
        self.vibration_ax = self.figure.add_subplot(212)
        self.vibration_ax.set_title('震动强度', fontsize=10)
        self.vibration_ax.set_ylabel('强度', fontsize=8)
        self.vibration_ax.set_xlabel('时间', fontsize=8)
        self.vibration_ax.grid(True, alpha=0.3)
        
        # 设置紧凑布局
        self.figure.tight_layout()
        
        # 创建canvas
        self.canvas = FigureCanvasTkAgg(self.figure, parent)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # 初始化图表数据
        self.setup_chart_data()
    
    def setup_chart_data(self):
        """初始化图表数据"""
        # 音频图表
        self.audio_line_low, = self.audio_ax.plot([], [], 'b-', label='低频', linewidth=1.5)
        self.audio_line_high, = self.audio_ax.plot([], [], 'r-', label='高频', linewidth=1.5)
        self.audio_ax.legend(fontsize=8)
        self.audio_ax.set_ylim(0, 1)
        
        # 震动图表
        self.vibration_line_left, = self.vibration_ax.plot([], [], 'b-', label='左马达', linewidth=1.5)
        self.vibration_line_right, = self.vibration_ax.plot([], [], 'r-', label='右马达', linewidth=1.5)
        self.vibration_ax.legend(fontsize=8)
        self.vibration_ax.set_ylim(0, 1)
    
    def setup_status_bar(self):
        """设置状态栏"""
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=5)
        
        self.status_label = ttk.Label(status_frame, text="就绪", style='Status.TLabel')
        self.status_label.pack(side=tk.LEFT)
        
        self.fps_label = ttk.Label(status_frame, text="FPS: 0", style='Status.TLabel')
        self.fps_label.pack(side=tk.RIGHT)
    
    # GUI事件处理方法
    def refresh_devices(self):
        """刷新音频设备列表"""
        try:
            devices = self.audio_processor.get_audio_devices()
            device_names = []
            system_audio_count = 0
            
            for device in devices:
                display_name = device['name']
                if device['is_system_audio']:
                    tag = "[系统音频]" if device.get('is_loopback') else "[混音/环回]"
                    suffix = "（当前默认输出）" if device.get('is_default_loopback') else ""
                    display_name = f"{tag} {display_name}{suffix}"
                    system_audio_count += 1
                else:
                    display_name = f"[麦克风] {display_name}"
                device_names.append(display_name)
            
            self.device_combo['values'] = device_names
            
            # 优先选择系统音频设备
            if system_audio_count > 0:
                for i, device in enumerate(devices):
                    if device['is_system_audio']:
                        self.device_combo.current(i)
                        self.audio_processor.device_index = device['index']
                        break
                status_msg = f"已发现 {system_audio_count} 个系统音频设备（WASAPI环回可直接抓系统播放的声音）"
            else:
                if devices:
                    self.device_combo.current(0)
                    self.audio_processor.device_index = devices[0]['index']
                status_msg = "未发现系统音频设备，请启用立体声混音或改用 WASAPI 环回设备"
            
            self.update_status(status_msg)
            
        except Exception as e:
            messagebox.showerror("错误", f"刷新设备列表失败: {e}")
    
    def on_device_changed(self, event=None):
        """设备选择改变"""
        try:
            selection = self.device_combo.current()
            if selection >= 0:
                devices = self.audio_processor.get_audio_devices()
                if selection < len(devices):
                    selected_device = devices[selection]
                    self.audio_processor.device_index = selected_device['index']
                    
                    if selected_device['is_system_audio']:
                        self.update_status(f"已选择系统音频设备: {selected_device['name']}")
                    else:
                        self.update_status(f"已选择输入设备: {selected_device['name']}")
        except Exception as e:
            print(f"设备切换错误: {e}")
    
    def toggle_conversion(self):
        """开始/停止音频转换"""
        if not self.is_running:
            self.start_conversion()
        else:
            self.stop_conversion()
    
    def start_conversion(self):
        """启动音频转换"""
        try:
            ok = self.audio_processor.start_recording()
            if not ok:
                # 采集没起来就不能装作在跑，否则就是"界面在转、手柄不震"
                err = getattr(self.audio_processor, 'last_error', None) or "未知原因"
                self.update_status(f"音频采集启动失败: {err}")
                messagebox.showerror(
                    "音频采集失败",
                    "没能打开音频采集，所以不会有震动。\n\n"
                    f"原因: {err}\n\n"
                    "请点【刷新设备】后重新选择，建议选 [系统音频] 开头的设备(WASAPI环回)。"
                )
                return
            
            self.is_running = True
            self.start_button.config(text="停止转换")
            kind = "系统音频" if getattr(self.audio_processor, 'capture_is_loopback', False) else "输入设备"
            self.update_status(f"正在运行音频转震动转换（采集源: {kind}）...")
            
            # 启动处理线程
            self.processing_thread = threading.Thread(target=self.audio_processing_loop, daemon=True)
            self.processing_thread.start()
            
        except Exception as e:
            messagebox.showerror("错误", f"启动失败: {e}")
    
    def stop_conversion(self):
        """停止音频转换"""
        self.is_running = False
        self.start_button.config(text="开始转换")
        self.update_status("已停止")
        
        self.audio_processor.stop_recording()
        self.vibration_mapper.stop_vibration()
    
    def test_vibration(self):
        """测试震动"""
        try:
            self.controller_manager.test_vibration_pattern('basic')
            self.update_status("震动测试完成")
        except Exception as e:
            messagebox.showerror("错误", f"震动测试失败: {e}")
    
    def emergency_stop(self):
        """紧急停止"""
        self.stop_conversion()
        self.controller_manager.emergency_stop()
        self.update_status("紧急停止执行完毕")
    
    # 参数更新方法
    def update_sensitivity(self, event=None):
        """更新敏感度参数"""
        low_sens = self.low_sens_var.get()
        high_sens = self.high_sens_var.get()
        overall = self.overall_var.get()
        
        self.vibration_mapper.low_freq_sensitivity = low_sens
        self.vibration_mapper.high_freq_sensitivity = high_sens
        self.vibration_mapper.overall_intensity = overall
        
        self.low_sens_label.config(text=f"{low_sens:.2f}")
        self.high_sens_label.config(text=f"{high_sens:.2f}")
        self.overall_label.config(text=f"{overall:.2f}")
    
    def update_thresholds_basic(self, event=None):
        """更新基础响应阈值"""
        low_threshold = self.low_threshold_var.get()
        high_threshold = self.high_threshold_var.get()
        
        self.vibration_mapper.min_low_freq_threshold = low_threshold
        self.vibration_mapper.min_high_freq_threshold = high_threshold
        
        self.low_threshold_label.config(text=f"{low_threshold:.3f}")
        self.high_threshold_label.config(text=f"{high_threshold:.3f}")
    
    def update_volume_range(self, event=None):
        """更新通用音量范围"""
        min_volume = self.min_volume_var.get()
        max_volume = self.max_volume_var.get()
        
        # 确保最小值小于最大值
        if min_volume >= max_volume:
            max_volume = min_volume + 0.1
            self.max_volume_var.set(max_volume)
        
        self.vibration_mapper.min_volume_threshold = min_volume
        self.vibration_mapper.max_volume_threshold = max_volume
        
        self.min_volume_label.config(text=f"{min_volume:.3f}")
        self.max_volume_label.config(text=f"{max_volume:.3f}")
    
    def update_sound_boosts(self, event=None):
        """更新声音增强参数"""
        explosion_boost = self.explosion_boost_var.get()
        metal_boost = self.metal_boost_var.get()
        
        self.vibration_mapper.set_sound_type_boosts(explosion_boost, metal_boost)
        
        self.explosion_boost_label.config(text=f"{explosion_boost:.2f}")
        self.metal_boost_label.config(text=f"{metal_boost:.2f}")
    
    def update_thresholds(self, event=None):
        """更新识别阈值"""
        explosion_thresh = self.explosion_threshold_var.get()
        metal_thresh = self.metal_threshold_var.get()
        
        self.vibration_mapper.classification_thresholds['explosion']['sub_bass'] = explosion_thresh
        self.vibration_mapper.classification_thresholds['metal_clash']['high_mid'] = metal_thresh
        
        self.explosion_threshold_label.config(text=f"{explosion_thresh:.2f}")
        self.metal_threshold_label.config(text=f"{metal_thresh:.2f}")
    
    def update_impact_settings(self, event=None):
        """更新冲击设置"""
        multiplier = self.impact_multiplier_var.get()
        duration = self.impact_duration_var.get()
        
        self.vibration_mapper.set_impact_settings(multiplier, duration)
        
        self.impact_multiplier_label.config(text=f"{multiplier:.2f}")
        self.impact_duration_label.config(text=f"{duration:.2f}")
    
    def update_detection_settings(self, event=None):
        """更新检测设置"""
        energy_thresh = self.energy_threshold_var.get()
        self.energy_threshold_label.config(text=f"{energy_thresh:.2f}")
        # 注意：这个参数需要传递给audio_processor的detect_audio_events方法
    
    def update_advanced_settings(self, event=None):
        """更新高级设置"""
        smoothing = self.smoothing_var.get()
        cutoff = self.cutoff_var.get()
        freq_diff = self.frequency_diff_var.get()
        
        # 更新震动映射器参数
        self.vibration_mapper.smoothing_factor = smoothing
        self.vibration_mapper.frequency_cutoff = int(cutoff)
        self.vibration_mapper.frequency_difference_factor = freq_diff
        
        # 重要：同时更新音频处理器的滤波器分离点
        if hasattr(self, 'audio_processor') and self.audio_processor:
            self.audio_processor.set_filter_cutoff_frequency(int(cutoff))
        
        self.smoothing_label.config(text=f"{smoothing:.2f}")
        self.cutoff_label.config(text=f"{int(cutoff)}")
        self.frequency_diff_label.config(text=f"{freq_diff:.2f}")
    
    def toggle_classification(self):
        """切换声音分类"""
        enabled = self.classification_enabled.get()
        self.vibration_mapper.enable_sound_classification = enabled
        self.update_status(f"声音识别已{'启用' if enabled else '禁用'}")
    
    def toggle_impact_enhancement(self):
        """切换冲击增强"""
        enabled = self.impact_enabled.get()
        self.vibration_mapper.enable_impact_enhancement = enabled
        self.update_status(f"冲击增强已{'启用' if enabled else '禁用'}")
    
    def refresh_controllers(self):
        """刷新手柄连接状态"""
        try:
            self.update_status("正在刷新手柄连接...")
            
            result = self.controller_manager.refresh_controllers()
            
            # 更新手柄状态显示
            self.update_controller_status()
            
            if result:
                connected_count = len(self.controller_manager.connected_controllers)
                if connected_count > 0:
                    messagebox.showinfo("刷新成功", f"检测到 {connected_count} 个手柄连接")
                    self.update_status(f"手柄刷新成功，检测到 {connected_count} 个连接")
                else:
                    messagebox.showwarning("刷新结果", "未检测到手柄连接")
                    self.update_status("手柄刷新完成，未检测到连接")
            else:
                messagebox.showwarning("刷新结果", "未检测到手柄连接")
                self.update_status("手柄刷新完成，未检测到连接")
                
        except Exception as e:
            messagebox.showerror("刷新失败", f"手柄刷新出错: {e}")
            self.update_status(f"手柄刷新失败: {e}")
    
    def force_vibration_test(self):
        """强制震动测试"""
        try:
            # 询问用户选择震动模式
            pattern = messagebox.askyesnocancel(
                "强制震动测试", 
                "选择震动模式:\n\n" +
                "「是」= 基础测试（左-右-双侧）\n" +
                "「否」= 脉冲模式（递增强度）\n" +
                "「取消」= 取消测试"
            )
            
            if pattern is None:  # 取消
                return
            elif pattern == True:  # 基础测试
                test_mode = 'basic'
                self.update_status("开始强制基础震动测试...")
            else:  # 脉冲模式
                test_mode = 'pulse'
                self.update_status("开始强制脉冲震动测试...")
            
            # 在新线程中执行测试，避免阻塞GUI
            def test_thread():
                try:
                    self.controller_manager.force_vibration_test(test_mode)
                    self.root.after_idle(lambda: self.update_status("强制震动测试完成"))
                    self.root.after_idle(lambda: messagebox.showinfo("测试完成", "强制震动测试已完成"))
                except Exception as e:
                    self.root.after_idle(lambda: self.update_status(f"强制震动测试失败: {e}"))
                    self.root.after_idle(lambda: messagebox.showerror("测试失败", f"强制震动测试失败: {e}"))
            
            threading.Thread(target=test_thread, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("测试失败", f"强制震动测试出错: {e}")
            self.update_status(f"强制震动测试失败: {e}")
    
    def force_stop_vibration(self):
        """强制停止震动"""
        try:
            self.update_status("强制停止所有震动...")
            success = self.controller_manager.stop_vibration(force=True)
            
            if success:
                messagebox.showinfo("停止成功", "已强制停止所有震动")
                self.update_status("已强制停止所有震动")
            else:
                messagebox.showwarning("停止失败", "强制停止震动失败，可能没有连接的手柄")
                self.update_status("强制停止震动失败")
                
        except Exception as e:
            messagebox.showerror("停止失败", f"强制停止震动出错: {e}")
            self.update_status(f"强制停止震动失败: {e}")
    
    def update_controller_status(self):
        """更新手柄状态显示"""
        try:
            if hasattr(self.controller_manager, 'connected_controllers'):
                connected_count = len(self.controller_manager.connected_controllers)
                
                if connected_count > 0:
                    status_text = f"已连接 {connected_count} 个手柄"
                    status_color = 'green'
                else:
                    status_text = "未检测到手柄"
                    status_color = 'red'
            else:
                status_text = "状态未知"
                status_color = 'gray'
            
            if hasattr(self, 'controller_status_label'):
                self.controller_status_label.config(text=status_text, foreground=status_color)
                
        except Exception as e:
            print(f"更新手柄状态失败: {e}")
    
    def update_slider_values_from_mapper(self):
        """从映射器更新滑块值"""
        params = self.vibration_mapper.get_parameters()
        
        self.low_sens_var.set(params['low_freq_sensitivity'])
        self.high_sens_var.set(params['high_freq_sensitivity'])
        self.overall_var.set(params['overall_intensity'])
        self.smoothing_var.set(params['smoothing_factor'])
        self.cutoff_var.set(params['frequency_cutoff'])
        
        # 设置阈值参数
        if 'min_low_freq_threshold' in params:
            self.low_threshold_var.set(params['min_low_freq_threshold'])
        if 'min_high_freq_threshold' in params:
            self.high_threshold_var.set(params['min_high_freq_threshold'])
        
        # 设置音量范围参数
        if 'min_volume_threshold' in params:
            self.min_volume_var.set(params['min_volume_threshold'])
        if 'max_volume_threshold' in params:
            self.max_volume_var.set(params['max_volume_threshold'])
        
        # 设置频率差参数（如果存在）
        if hasattr(self.vibration_mapper, 'frequency_difference_factor'):
            self.frequency_diff_var.set(self.vibration_mapper.frequency_difference_factor)
        
        # 更新标签
        self.update_sensitivity()
        self.update_thresholds_basic()
        self.update_volume_range()
        self.update_advanced_settings()
    
    # 音频处理循环
    def audio_processing_loop(self):
        """音频处理主循环"""
        while self.is_running:
            try:
                audio_data = self.audio_processor.get_latest_audio_data(timeout=0.01)
                if audio_data is not None:
                    # 分析音频数据
                    volume_analysis = self.audio_processor.get_volume_analysis(audio_data)
                    
                    # 处理震动映射（包含智能声音识别）
                    vibration_status = self.vibration_mapper.process_audio_frame(
                        volume_analysis, 
                        self.audio_processor, 
                        audio_data
                    )
                    
                    # 更新数据缓冲区
                    self.update_data_buffers(volume_analysis, vibration_status)
                    
            except Exception as e:
                if self.is_running:
                    print(f"音频处理错误: {e}")
                time.sleep(0.01)
    
    def update_data_buffers(self, volume_analysis, vibration_status):
        """更新数据缓冲区"""
        # 音频数据
        audio_data = {
            'low_freq': volume_analysis.get('smoothed_low_rms', 0),
            'high_freq': volume_analysis.get('smoothed_high_rms', 0),
            'total_rms': volume_analysis.get('smoothed_total_rms', 0)
        }
        
        self.audio_data_buffer.append(audio_data)
        if len(self.audio_data_buffer) > self.max_buffer_size:
            self.audio_data_buffer.pop(0)
        
        # 震动数据
        self.vibration_data_buffer.append(vibration_status)
        if len(self.vibration_data_buffer) > self.max_buffer_size:
            self.vibration_data_buffer.pop(0)
        
        # 声音类型历史
        sound_type = vibration_status.get('sound_type', 'normal')
        self.sound_type_history.append(sound_type)
        if len(self.sound_type_history) > 50:
            self.sound_type_history.pop(0)
    
    def start_monitoring(self):
        """启动实时监控"""
        self.monitoring_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
        self.monitoring_thread.start()
    
    def monitoring_loop(self):
        """监控循环"""
        while True:
            try:
                if self.is_running and len(self.vibration_data_buffer) > 0:
                    # 更新GUI显示
                    self.root.after_idle(self.update_realtime_display)
                    self.root.after_idle(self.update_charts)
                    
                    # 更新FPS
                    current_time = time.time()
                    if not hasattr(self, 'fps_times'):
                        self.fps_times = []
                    self.fps_times.append(current_time)
                    self.fps_times = [t for t in self.fps_times if current_time - t <= 1.0]
                    self.fps = len(self.fps_times)
                    
                    self.root.after_idle(lambda: self.fps_label.config(text=f"FPS: {self.fps:.1f}"))
                
                time.sleep(0.033)  # 约30Hz更新频率
                
            except Exception as e:
                print(f"监控循环错误: {e}")
                time.sleep(0.1)
    
    def update_realtime_display(self):
        """更新实时数据显示"""
        if not self.vibration_data_buffer:
            return
            
        latest_vibration = self.vibration_data_buffer[-1]
        latest_audio = self.audio_data_buffer[-1] if self.audio_data_buffer else {}
        
        # 更新音频数据
        self.low_freq_display.config(text=f"{latest_audio.get('low_freq', 0):.3f}")
        self.high_freq_display.config(text=f"{latest_audio.get('high_freq', 0):.3f}")
        
        # 更新震动数据
        left_intensity = latest_vibration.get('left_intensity', 0)
        right_intensity = latest_vibration.get('right_intensity', 0)
        left_motor_value = int(left_intensity * 65535)
        right_motor_value = int(right_intensity * 65535)
        
        self.left_motor_display.config(text=f"{left_motor_value} ({left_intensity*100:.1f}%)")
        self.right_motor_display.config(text=f"{right_motor_value} ({right_intensity*100:.1f}%)")
        
        # 更新声音识别状态
        sound_type = latest_vibration.get('sound_type', 'normal')
        impact_detected = latest_vibration.get('impact_detected', False)
        
        sound_type_names = {
            'normal': '🔇 静音',
            'explosion': '💥 爆炸',
            'metal_clash': '⚔️ 金属碰撞',
            'gunshot': '🔫 枪声',
            'drum_hit': '🥁 鼓声',
            'glass_break': '💎 玻璃破碎'
        }
        
        display_name = sound_type_names.get(sound_type, f"🎵 {sound_type}")
        self.sound_type_display.config(text=display_name)
        
        impact_text = "🔥 冲击中!" if impact_detected else "❌ 无冲击"
        self.impact_status_display.config(text=impact_text)
        
        # 更新频段显示
        self.update_frequency_bands_display(latest_vibration)
    
    def update_frequency_bands_display(self, vibration_status):
        """更新频段显示"""
        # 这里需要从audio_processor获取频段分析数据
        # 为了演示，我们先使用模拟数据
        bands_data = {
            'sub_bass': vibration_status.get('left_intensity', 0) * 0.8,
            'bass': vibration_status.get('left_intensity', 0) * 0.6,
            'low_mid': (vibration_status.get('left_intensity', 0) + vibration_status.get('right_intensity', 0)) * 0.5,
            'mid': (vibration_status.get('left_intensity', 0) + vibration_status.get('right_intensity', 0)) * 0.4,
            'high_mid': vibration_status.get('right_intensity', 0) * 0.6,
            'treble': vibration_status.get('right_intensity', 0) * 0.8
        }
        
        for band_key, value in bands_data.items():
            if band_key in self.band_displays:
                self.band_displays[band_key]['progress']['value'] = value * 100
                self.band_displays[band_key]['label'].config(text=f"{value:.2f}")
    
    def update_charts(self):
        """更新图表"""
        if len(self.audio_data_buffer) < 2:
            return
        
        try:
            # 准备数据
            time_data = list(range(len(self.audio_data_buffer)))
            low_freq_data = [data['low_freq'] for data in self.audio_data_buffer]
            high_freq_data = [data['high_freq'] for data in self.audio_data_buffer]
            
            left_vibration_data = [data.get('left_intensity', 0) for data in self.vibration_data_buffer]
            right_vibration_data = [data.get('right_intensity', 0) for data in self.vibration_data_buffer]
            
            # 更新音频图表
            self.audio_line_low.set_data(time_data, low_freq_data)
            self.audio_line_high.set_data(time_data, high_freq_data)
            self.audio_ax.relim()
            self.audio_ax.autoscale_view()
            
            # 更新震动图表
            self.vibration_line_left.set_data(time_data, left_vibration_data)
            self.vibration_line_right.set_data(time_data, right_vibration_data)
            self.vibration_ax.relim()
            self.vibration_ax.autoscale_view()
            
            # 重绘
            self.canvas.draw_idle()
            
        except Exception as e:
            print(f"更新图表错误: {e}")
    
    # 配置管理
    def save_configuration(self):
        """保存配置到config文件夹，可命名"""
        try:
            # 弹出命名对话框
            config_name = simpledialog.askstring(
                "保存配置",
                "请输入配置名称:",
                initialvalue="自定义配置"
            )
            
            if not config_name:
                return  # 用户取消
            
            # 确保config文件夹存在
            os.makedirs("config", exist_ok=True)
            
            # 构建配置数据
            config = {
                'name': config_name,
                'created_time': time.strftime("%Y-%m-%d %H:%M:%S"),
                'vibration_mapper_params': self.vibration_mapper.get_parameters(),
                'sound_classification': {
                    'enabled': self.classification_enabled.get(),
                    'explosion_boost': self.explosion_boost_var.get(),
                    'metal_boost': self.metal_boost_var.get(),
                    'explosion_threshold': self.explosion_threshold_var.get(),
                    'metal_threshold': self.metal_threshold_var.get()
                },
                'impact_enhancement': {
                    'enabled': self.impact_enabled.get(),
                    'multiplier': self.impact_multiplier_var.get(),
                    'duration': self.impact_duration_var.get(),
                    'energy_threshold': self.energy_threshold_var.get()
                },
                'advanced_settings': {
                    'frequency_difference_factor': self.frequency_diff_var.get(),
                    'min_low_freq_threshold': self.low_threshold_var.get(),
                    'min_high_freq_threshold': self.high_threshold_var.get(),
                    'min_volume_threshold': self.min_volume_var.get(),
                    'max_volume_threshold': self.max_volume_var.get()
                },
            }
            
            # 生成文件名（避免特殊字符）
            safe_name = "".join(c for c in config_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"config/{safe_name}.json"
            
            # 如果文件已存在，询问是否覆盖
            if os.path.exists(filename):
                if not messagebox.askyesno("确认覆盖", f"配置 '{config_name}' 已存在，是否覆盖？"):
                    return
            
            # 保存文件
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            self.update_status(f"配置 '{config_name}' 已保存")
            
            # 刷新配置列表
            self.refresh_config_list()
            
            # 自动选中刚保存的配置
            self.config_var.set(config_name)
            
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败: {e}")
    
    def refresh_config_list(self):
        """刷新配置列表"""
        try:
            # 确保config文件夹存在
            os.makedirs("config", exist_ok=True)
            
            # 扫描config文件夹中的.json文件
            config_files = glob.glob("config/*.json")
            config_names = []
            
            for file_path in config_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                        name = config_data.get('name', os.path.splitext(os.path.basename(file_path))[0])
                        config_names.append(name)
                except:
                    # 如果文件损坏，使用文件名
                    name = os.path.splitext(os.path.basename(file_path))[0]
                    config_names.append(name)
            
            # 更新下拉框
            self.config_combo['values'] = sorted(config_names)
            
            if not config_names:
                self.config_combo.set("")
            elif not self.config_var.get() or self.config_var.get() not in config_names:
                # 如果当前选中的配置不存在，清空选择
                self.config_var.set("")
                
        except Exception as e:
            print(f"刷新配置列表失败: {e}")
    
    def on_config_selected(self, event=None):
        """配置选择改变事件"""
        # 这里可以添加预览功能，目前暂时留空
        pass
    
    def load_selected_configuration(self):
        """加载选中的配置"""
        config_name = self.config_var.get()
        if not config_name:
            messagebox.showwarning("提示", "请先选择一个配置")
            return
            
        self.load_configuration_by_name(config_name)
    
    def load_configuration_by_name(self, config_name):
        """根据配置名称加载配置"""
        try:
            # 查找对应的配置文件
            config_files = glob.glob("config/*.json")
            target_file = None
            
            for file_path in config_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                        if config_data.get('name', os.path.splitext(os.path.basename(file_path))[0]) == config_name:
                            target_file = file_path
                            break
                except:
                    continue
            
            if not target_file:
                messagebox.showerror("错误", f"找不到配置: {config_name}")
                return
            
            # 加载配置文件
            with open(target_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 应用震动映射器参数
            if 'vibration_mapper_params' in config:
                self.vibration_mapper.set_parameters(**config['vibration_mapper_params'])
                self.update_slider_values_from_mapper()
            
            # 应用声音分类设置
            if 'sound_classification' in config:
                sc = config['sound_classification']
                self.classification_enabled.set(sc.get('enabled', False))
                self.explosion_boost_var.set(sc.get('explosion_boost', 2.5))
                self.metal_boost_var.set(sc.get('metal_boost', 2.0))
                self.explosion_threshold_var.set(sc.get('explosion_threshold', 0.6))
                self.metal_threshold_var.set(sc.get('metal_threshold', 0.4))
                self.update_sound_boosts()
                self.update_thresholds()
                
            # 应用冲击增强设置
            if 'impact_enhancement' in config:
                ie = config['impact_enhancement']
                self.impact_enabled.set(ie.get('enabled', False))
                self.impact_multiplier_var.set(ie.get('multiplier', 3.0))
                self.impact_duration_var.set(ie.get('duration', 0.15))
                self.energy_threshold_var.set(ie.get('energy_threshold', 1.5))
                self.update_impact_settings()
                self.update_detection_settings()
            
            # 应用高级设置
            if 'advanced_settings' in config:
                adv = config['advanced_settings']
                self.frequency_diff_var.set(adv.get('frequency_difference_factor', 1.0))
                self.low_threshold_var.set(adv.get('min_low_freq_threshold', 0.15))
                self.high_threshold_var.set(adv.get('min_high_freq_threshold', 0.05))
                self.min_volume_var.set(adv.get('min_volume_threshold', 0.03))
                self.max_volume_var.set(adv.get('max_volume_threshold', 1.0))
                self.update_advanced_settings()
                self.update_thresholds_basic()
                self.update_volume_range()
            
            # 确保开关状态同步
            self.toggle_classification()
            self.toggle_impact_enhancement()
            
            # 显示配置信息
            created_time = config.get('created_time', '未知')
            self.update_status(f"已加载配置: {config_name} (创建时间: {created_time})")
            
        except Exception as e:
            messagebox.showerror("错误", f"加载配置失败: {e}")
    
    def delete_configuration(self):
        """删除选中的配置"""
        config_name = self.config_var.get()
        if not config_name:
            messagebox.showwarning("提示", "请先选择一个配置")
            return
        
        # 确认删除
        if not messagebox.askyesno("确认删除", f"确定要删除配置 '{config_name}' 吗？"):
            return
            
        try:
            # 查找对应的配置文件
            config_files = glob.glob("config/*.json")
            
            for file_path in config_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                        if config_data.get('name', os.path.splitext(os.path.basename(file_path))[0]) == config_name:
                            os.remove(file_path)
                            self.update_status(f"已删除配置: {config_name}")
                            
                            # 刷新列表并清空选择
                            self.refresh_config_list()
                            self.config_var.set("")
                            return
                except:
                    continue
            
            messagebox.showerror("错误", f"找不到配置文件: {config_name}")
            
        except Exception as e:
            messagebox.showerror("错误", f"删除配置失败: {e}")
    
    def load_configuration(self):
        """加载配置"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 应用震动映射参数
            if 'vibration_mapper_params' in config:
                self.vibration_mapper.set_parameters(**config['vibration_mapper_params'])
                self.update_slider_values_from_mapper()
            
            # 应用声音分类设置
            if 'sound_classification' in config:
                sc = config['sound_classification']
                self.classification_enabled.set(sc.get('enabled', True))
                self.explosion_boost_var.set(sc.get('explosion_boost', 2.5))
                self.metal_boost_var.set(sc.get('metal_boost', 2.0))
                self.explosion_threshold_var.set(sc.get('explosion_threshold', 0.3))
                self.metal_threshold_var.set(sc.get('metal_threshold', 0.25))
                self.update_sound_boosts()
                self.update_thresholds()
            
            # 应用冲击增强设置
            if 'impact_enhancement' in config:
                ie = config['impact_enhancement']
                self.impact_enabled.set(ie.get('enabled', True))
                self.impact_multiplier_var.set(ie.get('multiplier', 3.0))
                self.impact_duration_var.set(ie.get('duration', 0.15))
                self.energy_threshold_var.set(ie.get('energy_threshold', 5.0))
                self.update_impact_settings()
                self.update_detection_settings()
            
            # 应用高级设置
            if 'advanced_settings' in config:
                adv = config['advanced_settings']
                self.frequency_diff_var.set(adv.get('frequency_difference_factor', 0.0))
                self.low_threshold_var.set(adv.get('min_low_freq_threshold', 0.01))
                self.high_threshold_var.set(adv.get('min_high_freq_threshold', 0.01))
                self.min_volume_var.set(adv.get('min_volume_threshold', 0.01))
                self.max_volume_var.set(adv.get('max_volume_threshold', 1.0))
                self.update_advanced_settings()
                self.update_thresholds_basic()
                self.update_volume_range()
            
             
            self.update_status(f"配置已从 {self.config_file} 加载")
            
        except Exception as e:
            messagebox.showerror("错误", f"加载配置失败: {e}")
    
    def _load_default_configuration(self):
        """加载默认配置文件"""
        try:
            with open('default_config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 应用震动映射参数
            if 'vibration_mapper_params' in config:
                self.vibration_mapper.set_parameters(**config['vibration_mapper_params'])
                self.update_slider_values_from_mapper()
            
            # 应用声音分类设置
            if 'sound_classification' in config:
                sc = config['sound_classification']
                self.classification_enabled.set(sc.get('enabled', False))
                self.explosion_boost_var.set(sc.get('explosion_boost', 2.5))
                self.metal_boost_var.set(sc.get('metal_boost', 2.0))
                self.explosion_threshold_var.set(sc.get('explosion_threshold', 0.3))
                self.metal_threshold_var.set(sc.get('metal_threshold', 0.25))
                self.update_sound_boosts()
                self.update_thresholds()
            
            # 应用冲击增强设置
            if 'impact_enhancement' in config:
                ie = config['impact_enhancement']
                self.impact_enabled.set(ie.get('enabled', False))
                self.impact_multiplier_var.set(ie.get('multiplier', 3.0))
                self.impact_duration_var.set(ie.get('duration', 0.15))
                self.energy_threshold_var.set(ie.get('energy_threshold', 5.0))
                self.update_impact_settings()
                self.update_detection_settings()
            
            # 应用高级设置
            if 'advanced_settings' in config:
                adv = config['advanced_settings']
                self.frequency_diff_var.set(adv.get('frequency_difference_factor', 1.0))
                self.low_threshold_var.set(adv.get('min_low_freq_threshold', 0.15))
                self.high_threshold_var.set(adv.get('min_high_freq_threshold', 0.05))
                self.min_volume_var.set(adv.get('min_volume_threshold', 0.03))
                self.max_volume_var.set(adv.get('max_volume_threshold', 1.0))
                self.update_advanced_settings()
                self.update_thresholds_basic()
                self.update_volume_range()
            
            
            # 确保开关状态同步
            self.toggle_classification()
            self.toggle_impact_enhancement()
            
            return True
            
        except FileNotFoundError:
            messagebox.showerror("错误", "默认配置文件 'default_config.json' 未找到！\n将使用程序内置的默认值。")
            return False
        except json.JSONDecodeError as e:
            messagebox.showerror("错误", f"默认配置文件格式错误: {e}\n将使用程序内置的默认值。")
            return False
        except Exception as e:
            messagebox.showerror("错误", f"加载默认配置失败: {e}\n将使用程序内置的默认值。")
            return False
    
    def _apply_builtin_defaults(self):
        """应用程序内置的默认值（作为备用方案）"""
        # 重置震动映射器（使用默认值）
        # 已移除预设功能，直接设置默认参数值
        
        # 重置GUI控件
        self.classification_enabled.set(False)
        self.impact_enabled.set(False)
        self.explosion_boost_var.set(2.5)
        self.metal_boost_var.set(2.0)
        self.explosion_threshold_var.set(0.3)
        self.metal_threshold_var.set(0.25)
        self.impact_multiplier_var.set(3.0)
        self.impact_duration_var.set(0.15)
        self.energy_threshold_var.set(5.0)
        self.frequency_diff_var.set(1.0)
        self.low_threshold_var.set(0.15)
        self.high_threshold_var.set(0.05)
        self.min_volume_var.set(0.03)
        self.max_volume_var.set(1.0)
        
        # 设置正确的平滑因子
        self.vibration_mapper.smoothing_factor = 0.0
        self.smoothing_var.set(0.0)
        
        # 更新所有参数
        self.update_slider_values_from_mapper()
        self.update_sound_boosts()
        self.update_thresholds()
        self.update_impact_settings()
        self.update_thresholds_basic()
        self.update_volume_range()
        self.toggle_classification()
        self.toggle_impact_enhancement()
    
    def reset_to_defaults(self):
        """重置为默认值"""
        if messagebox.askyesno("确认", "确定要重置所有参数为默认值吗？\n将从 default_config.json 加载默认配置。"):
            # 首先尝试加载默认配置文件
            if self._load_default_configuration():
                self.update_status("已从 default_config.json 重置为默认值")
            else:
                # 如果加载失败，使用内置默认值
                self._apply_builtin_defaults()
                self.update_status("已重置为程序内置默认值")
    
    def update_status(self, message):
        """更新状态栏"""
        self.status_label.config(text=message)
    
    def on_closing(self):
        """关闭事件处理"""
        self.stop_conversion()
        self.root.quit()
        self.root.destroy()
    
    def run(self):
        """运行GUI主循环"""
        # 初始化设备
        self.refresh_devices()
        
        # 注册关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 启动主循环
        self.root.mainloop()

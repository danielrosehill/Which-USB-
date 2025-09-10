#!/usr/bin/env python3
import os
import subprocess
import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QWidget, QPushButton, QTextEdit, QLabel, QGroupBox,
                             QMessageBox, QProgressBar, QFrame, QScrollArea, QStackedWidget)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer, QUrl
from PyQt6.QtGui import QFont, QTextCharFormat, QColor, QClipboard, QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from typing import Dict, List, Tuple
from dataclasses import dataclass
import time
import tempfile
import urllib.request

@dataclass
class USBDevice:
    bus: str
    device: str
    vendor_id: str
    product_id: str
    description: str

class ImageLoader(QThread):
    image_loaded = pyqtSignal(str, QPixmap)  # url, pixmap
    
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.finished.connect(self.deleteLater)  # Clean up thread when finished
    
    def run(self):
        try:
            # Download image to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
                urllib.request.urlretrieve(self.url, temp_file.name)
                pixmap = QPixmap(temp_file.name)
                if not pixmap.isNull():
                    self.image_loaded.emit(self.url, pixmap)
                os.unlink(temp_file.name)
        except Exception as e:
            print(f"Failed to load image from {self.url}: {e}")

class LoadingThread(QThread):
    progress_update = pyqtSignal(int)
    loading_finished = pyqtSignal()
    
    def __init__(self, duration_ms=3000):
        super().__init__()
        self.duration_ms = duration_ms
        self.finished.connect(self.deleteLater)
    
    def run(self):
        steps = 100
        step_duration = self.duration_ms / steps / 1000.0  # Convert to seconds
        
        for i in range(steps + 1):
            self.progress_update.emit(i)
            if i < steps:
                time.sleep(step_duration)
        
        self.loading_finished.emit()

class CountdownThread(QThread):
    countdown_update = pyqtSignal(int)
    countdown_finished = pyqtSignal()
    
    def __init__(self, seconds=3):
        super().__init__()
        self.seconds = seconds
    
    def run(self):
        for i in range(self.seconds, 0, -1):
            self.countdown_update.emit(i)
            time.sleep(1)
        self.countdown_finished.emit()

class USBCaptureThread(QThread):
    finished = pyqtSignal(list)
    
    def run(self):
        devices = self.run_lsusb()
        self.finished.emit(devices)
    
    def run_lsusb(self) -> List[USBDevice]:
        """Run lsusb and parse the output into USBDevice objects."""
        try:
            result = subprocess.run(['lsusb'], capture_output=True, text=True, check=True)
            devices = []
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 6:
                    bus = parts[1].strip(':')
                    device = parts[3].strip(':')
                    vendor_product = parts[5].split(':')
                    if len(vendor_product) == 2:
                        vendor_id, product_id = vendor_product
                        description = ' '.join(parts[6:]) if len(parts) > 6 else 'Unknown device'
                        devices.append(USBDevice(bus, device, vendor_id, product_id, description))
            return devices
        except subprocess.CalledProcessError:
            return []

class USBMonitorThread(QThread):
    device_change_detected = pyqtSignal(list)
    
    def __init__(self, baseline_devices, monitor_type='disconnect'):
        super().__init__()
        self.baseline_devices = baseline_devices
        self.monitor_type = monitor_type  # 'disconnect' or 'connect'
        self.running = True
        
    def run(self):
        """Continuously monitor for USB device changes"""
        while self.running:
            current_devices = self.run_lsusb()
            
            if self.monitor_type == 'disconnect':
                # Check if any device was removed
                if len(current_devices) < len(self.baseline_devices):
                    # Device was disconnected
                    self.device_change_detected.emit(current_devices)
                    break
            else:  # connect
                # Check if any device was added
                if len(current_devices) > len(self.baseline_devices):
                    # Device was connected
                    self.device_change_detected.emit(current_devices)
                    break
            
            time.sleep(0.5)  # Check every 500ms for responsive detection
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
    
    def run_lsusb(self) -> List[USBDevice]:
        """Run lsusb and parse the output into USBDevice objects."""
        try:
            result = subprocess.run(['lsusb'], capture_output=True, text=True, check=True)
            devices = []
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 6:
                    bus = parts[1].strip(':')
                    device = parts[3].strip(':')
                    vendor_product = parts[5].split(':')
                    if len(vendor_product) == 2:
                        vendor_id, product_id = vendor_product
                        description = ' '.join(parts[6:]) if len(parts) > 6 else 'Unknown device'
                        devices.append(USBDevice(bus, device, vendor_id, product_id, description))
            return devices
        except subprocess.CalledProcessError:
            return []

class WhichUSBGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Which USB? - Device Identifier")
        self.setGeometry(100, 100, 800, 600)
        
        # Data storage
        self.first_capture = []
        self.second_capture = []
        self.identified_device = None
        self.detailed_inspection_data = None
        self.monitor_thread = None
        
        # Image URLs from data file
        self.image_urls = {
            'header': 'https://res.cloudinary.com/drrvnflqy/image/upload/v1757520216/header_fkixbf.png',
            'found': 'https://res.cloudinary.com/drrvnflqy/image/upload/v1757520355/found-it_oqpaix.png',
            'disconnect': 'https://res.cloudinary.com/drrvnflqy/image/upload/v1757520429/disconnect_eupmh1.jpg',
            'attach': 'https://res.cloudinary.com/drrvnflqy/image/upload/v1757520657/attach_xd2tge.png',
            'loading': 'https://res.cloudinary.com/drrvnflqy/image/upload/v1757520848/loading_z6swvg.png'
        }
        
        # Image cache
        self.loaded_images = {}
        
        self.setup_ui()
        self.load_images()
    
    def resizeEvent(self, event):
        """Handle window resize events to rescale images"""
        super().resizeEvent(event)
        # Note: Images now use fixed pixel sizes, so no rescaling needed on resize
    
    def load_images(self):
        """Load all images from URLs"""
        self.image_loaders = []  # Keep references to prevent garbage collection
        for name, url in self.image_urls.items():
            loader = ImageLoader(url)
            loader.image_loaded.connect(self.on_image_loaded)
            self.image_loaders.append(loader)
            loader.start()
    
    def on_image_loaded(self, url, pixmap):
        """Handle loaded image"""
        # Find which image this is
        for name, image_url in self.image_urls.items():
            if image_url == url:
                self.loaded_images[name] = pixmap
                # Update header image on loading screen if available
                if name == 'header' and hasattr(self, 'header_image_label'):
                    self.scale_and_set_image(self.header_image_label, pixmap, 600)  # 600px width
                # If this is the found image and we're on the results screen, update it
                elif name == 'found' and hasattr(self, 'found_image_label') and self.stacked_widget.currentIndex() == 3:
                    self.scale_and_set_image(self.found_image_label, pixmap, 200)  # 200px width
                break
    
    def show_floating_image(self, image_name, side='left'):
        """Show a floating image on the specified side"""
        if image_name in self.loaded_images:
            pixmap = self.loaded_images[image_name]
            
            if side == 'left':
                self.scale_and_set_image(self.left_image_label, pixmap, 400)  # 400px width
                self.left_image_label.show()
                self.right_image_label.hide()
            else:
                self.scale_and_set_image(self.right_image_label, pixmap, 400)  # 400px width
                self.right_image_label.show()
                self.left_image_label.hide()
    
    def show_loading_image(self):
        """Show the loading image in the center"""
        if 'loading' in self.loaded_images:
            pixmap = self.loaded_images['loading']
            self.scale_and_set_image(self.loading_image_label, pixmap, 300)  # 300px width
            self.loading_image_label.show()
    
    def scale_and_set_image(self, label, pixmap, max_width, max_height=None):
        """Scale image to fixed pixel size and set it to the label"""
        if max_height is None:
            max_height = max_width  # Square if height not specified
        scaled_pixmap = pixmap.scaled(max_width, max_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        label.setPixmap(scaled_pixmap)
    
    def hide_all_workflow_images(self):
        """Hide all workflow images"""
        self.left_image_label.hide()
        self.right_image_label.hide()
        self.loading_image_label.hide()
    
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create stacked widget for different screens
        self.stacked_widget = QStackedWidget()
        central_widget_layout = QVBoxLayout(central_widget)
        central_widget_layout.addWidget(self.stacked_widget)
        
        # Create screens
        self.create_loading_screen()
        self.create_welcome_screen()
        self.create_workflow_screen()
        self.create_results_screen()
        
        # Add footer
        self.create_footer(central_widget_layout)
        
        # Start with loading screen
        self.start_loading_sequence()
    
    def create_loading_screen(self):
        """Create the loading screen with progress bar"""
        loading_widget = QWidget()
        layout = QVBoxLayout(loading_widget)
        layout.setSpacing(40)
        layout.setContentsMargins(50, 50, 50, 50)
        
        # Header image (if available)
        self.header_image_label = QLabel()
        self.header_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if 'header' in self.loaded_images:
            self.scale_and_set_image(self.header_image_label, self.loaded_images['header'], 600)
        layout.addWidget(self.header_image_label)
        
        # Loading message
        self.loading_message = QLabel("Loading...")
        self.loading_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_message.setFont(QFont("Arial", 16))
        self.loading_message.setStyleSheet("color: #666666; margin-bottom: 20px;")
        layout.addWidget(self.loading_message)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #1976D2;
                border-radius: 8px;
                text-align: center;
                font-weight: bold;
                color: white;
                background-color: #f0f0f0;
                height: 30px;
            }
            QProgressBar::chunk {
                background-color: #1976D2;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        layout.addStretch()
        self.stacked_widget.addWidget(loading_widget)
    
    def start_loading_sequence(self):
        """Start the 3-second loading sequence"""
        self.stacked_widget.setCurrentIndex(0)  # Show loading screen
        
        # Start loading thread
        self.loading_thread = LoadingThread(3000)  # 3 seconds
        self.loading_thread.progress_update.connect(self.update_progress)
        self.loading_thread.loading_finished.connect(self.loading_complete)
        self.loading_thread.start()
    
    def update_progress(self, value):
        """Update the progress bar"""
        self.progress_bar.setValue(value)
        if value < 100:
            self.loading_message.setText(f"Loading... {value}%")
        else:
            self.loading_message.setText("Ready!")
    
    def loading_complete(self):
        """Handle loading completion"""
        self.stacked_widget.setCurrentIndex(1)  # Switch to welcome screen
    
    def create_welcome_screen(self):
        """Create the initial welcome screen"""
        welcome_widget = QWidget()
        layout = QVBoxLayout(welcome_widget)
        layout.setSpacing(30)
        layout.setContentsMargins(50, 50, 50, 50)
        
        # Greeting
        greeting = QLabel("Hi there! I'm here to help you identify your USB device!")
        greeting.setAlignment(Qt.AlignmentFlag.AlignCenter)
        greeting.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        greeting.setStyleSheet("color: #2E7D32; margin-bottom: 20px;")
        greeting.setWordWrap(True)
        layout.addWidget(greeting)
        
        # Question
        question = QLabel("Is the device you're trying to identify already connected to your computer by USB?")
        question.setAlignment(Qt.AlignmentFlag.AlignCenter)
        question.setFont(QFont("Arial", 14))
        question.setStyleSheet("color: #424242; margin-bottom: 30px;")
        question.setWordWrap(True)
        layout.addWidget(question)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)
        
        self.yes_btn = QPushButton("Yes, it's connected")
        self.yes_btn.clicked.connect(self.device_connected_workflow)
        self.yes_btn.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.yes_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 15px 30px;
                min-width: 200px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        self.no_btn = QPushButton("No, It's Not Connected")
        self.no_btn.clicked.connect(self.device_not_connected_workflow)
        self.no_btn.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.no_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 15px 30px;
                min-width: 200px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        
        button_layout.addWidget(self.yes_btn)
        button_layout.addWidget(self.no_btn)
        layout.addLayout(button_layout)
        
        layout.addStretch()
        self.stacked_widget.addWidget(welcome_widget)
    
    def create_workflow_screen(self):
        """Create the workflow execution screen"""
        workflow_widget = QWidget()
        layout = QVBoxLayout(workflow_widget)
        layout.setSpacing(30)
        layout.setContentsMargins(50, 50, 50, 50)
        
        # Main content area with horizontal layout for floating images
        content_frame = QFrame()
        content_layout = QHBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Left floating image (initially hidden)
        self.left_image_label = QLabel()
        self.left_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.left_image_label.hide()
        content_layout.addWidget(self.left_image_label)
        
        # Center content area
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setSpacing(20)
        
        # Status message
        self.workflow_status = QLabel()
        self.workflow_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.workflow_status.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.workflow_status.setStyleSheet("color: #1976D2; margin-bottom: 20px;")
        self.workflow_status.setWordWrap(True)
        center_layout.addWidget(self.workflow_status)
        
        # Loading image (initially hidden)
        self.loading_image_label = QLabel()
        self.loading_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_image_label.hide()
        center_layout.addWidget(self.loading_image_label)
        
        # Countdown display
        self.countdown_label = QLabel()
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown_label.setFont(QFont("Arial", 48, QFont.Weight.Bold))
        self.countdown_label.setStyleSheet("color: #FF5722; margin: 20px;")
        center_layout.addWidget(self.countdown_label)
        
        content_layout.addWidget(center_widget)
        
        # Right floating image (initially hidden)
        self.right_image_label = QLabel()
        self.right_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.right_image_label.hide()
        content_layout.addWidget(self.right_image_label)
        
        layout.addWidget(content_frame)
        
        # Success message (initially hidden)
        self.success_frame = QFrame()
        self.success_frame.setStyleSheet("""
            QFrame {
                background-color: #E8F5E8;
                border: 2px solid #4CAF50;
                border-radius: 12px;
                padding: 20px;
                margin: 20px;
            }
        """)
        self.success_frame.hide()
        
        success_layout = QVBoxLayout(self.success_frame)
        
        success_icon = QLabel("✅")
        success_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        success_icon.setFont(QFont("Arial", 36))
        success_layout.addWidget(success_icon)
        
        self.success_message = QLabel()
        self.success_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.success_message.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.success_message.setStyleSheet("color: #2E7D32;")
        success_layout.addWidget(self.success_message)
        
        layout.addWidget(self.success_frame)
        
        # View Results button (initially hidden)
        self.view_results_btn = QPushButton("View Results")
        self.view_results_btn.clicked.connect(self.show_results)
        self.view_results_btn.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.view_results_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 15px 40px;
                min-width: 200px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        self.view_results_btn.hide()
        layout.addWidget(self.view_results_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Back button
        self.back_btn = QPushButton("← Back")
        self.back_btn.clicked.connect(self.show_welcome)
        self.back_btn.setFont(QFont("Arial", 12))
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: #757575;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #616161;
            }
        """)
        layout.addWidget(self.back_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        
        layout.addStretch()
        self.stacked_widget.addWidget(workflow_widget)
    
    def create_results_screen(self):
        """Create the results display screen"""
        results_widget = QWidget()
        layout = QVBoxLayout(results_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Header with found image
        header_frame = QFrame()
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Found image on the left
        self.found_image_label = QLabel()
        self.found_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if 'found' in self.loaded_images:
            self.scale_and_set_image(self.found_image_label, self.loaded_images['found'], 200)
        header_layout.addWidget(self.found_image_label)
        
        # Header text
        header = QLabel("Your Identified Device")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        header.setStyleSheet("color: #1976D2; margin-bottom: 30px;")
        header_layout.addWidget(header)
        
        # Spacer on the right for balance
        spacer_label = QLabel()
        spacer_label.setMaximumWidth(100)
        header_layout.addWidget(spacer_label)
        
        layout.addWidget(header_frame)
        
        # Device cards container
        self.device_cards_container = QWidget()
        self.device_cards_layout = QVBoxLayout(self.device_cards_container)
        self.device_cards_layout.setSpacing(15)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.device_cards_container)
        layout.addWidget(scroll_area)
        
        # Back to start button
        self.restart_btn = QPushButton("Identify Another Device")
        self.restart_btn.clicked.connect(self.restart_app)
        self.restart_btn.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.restart_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 30px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        layout.addWidget(self.restart_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.stacked_widget.addWidget(results_widget)
    
    def create_footer(self, parent_layout):
        """Create footer with attribution"""
        footer = QLabel("Utility: Daniel Rosehill (danielrosehill.com)")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setFont(QFont("Arial", 10))
        footer.setStyleSheet("color: #757575; padding: 10px; border-top: 1px solid #E0E0E0;")
        parent_layout.addWidget(footer)
    
    def device_connected_workflow(self):
        """Handle workflow when device is already connected"""
        self.stacked_widget.setCurrentIndex(2)  # Switch to workflow screen
        self.workflow_status.setText("Great! Keep it there while I grab lsusb")
        self.countdown_label.hide()
        self.success_frame.hide()
        self.view_results_btn.hide()
        
        # Show loading image
        self.hide_all_workflow_images()
        self.show_loading_image()
        
        # Capture initial state
        self.capture_thread = USBCaptureThread()
        self.capture_thread.finished.connect(self.first_capture_connected_complete)
        self.capture_thread.start()
    
    def first_capture_connected_complete(self, devices):
        """Handle completion of first capture in connected workflow"""
        self.first_capture = devices
        self.workflow_status.setText("Analyzing connected device before disconnection...")
        self.countdown_label.hide()
        
        # Find the most likely target device (newest or most recently connected)
        # For now, we'll analyze all devices and let user choose later
        # Start detailed inspection of connected devices
        self.start_pre_disconnect_analysis()
    
    def device_not_connected_workflow(self):
        """Handle workflow when device is not connected"""
        self.stacked_widget.setCurrentIndex(2)  # Switch to workflow screen
        self.workflow_status.setText("Great. When the countdown reaches zero please connect the device you are trying to identify")
        self.countdown_label.show()
        self.success_frame.hide()
        self.view_results_btn.hide()
        
        # Show attach image on the left
        self.hide_all_workflow_images()
        self.show_floating_image('attach', 'left')
        
        # Capture initial state (without device)
        self.capture_thread = USBCaptureThread()
        self.capture_thread.finished.connect(self.first_capture_not_connected_complete)
        self.capture_thread.start()
    
    def first_capture_not_connected_complete(self, devices):
        """Handle completion of first capture in not connected workflow"""
        self.first_capture = devices
        
        # Start countdown
        self.countdown_thread = CountdownThread(3)
        self.countdown_thread.countdown_update.connect(self.update_countdown)
        self.countdown_thread.countdown_finished.connect(self.countdown_finished_not_connected)
        self.countdown_thread.start()
    
    def update_countdown(self, seconds):
        """Update countdown display"""
        self.countdown_label.setText(str(seconds))
    
    def countdown_finished_connected(self):
        """Handle countdown finish for connected workflow (disconnect device)"""
        self.countdown_label.hide()
        self.workflow_status.setText("Waiting for device disconnection...")
        
        # Start monitoring for disconnect
        self.start_disconnect_monitoring()
    
    def countdown_finished_not_connected(self):
        """Handle countdown finish for not connected workflow (connect device)"""
        self.countdown_label.hide()
        self.workflow_status.setText("Waiting for device connection...")
        
        # Start monitoring for connect
        self.start_connect_monitoring()
    
    def start_disconnect_monitoring(self):
        """Start monitoring for device disconnection"""
        if self.monitor_thread:
            self.monitor_thread.stop()
            self.monitor_thread.wait()
        
        self.monitor_thread = USBMonitorThread(self.first_capture, 'disconnect')
        self.monitor_thread.device_change_detected.connect(self.on_disconnect_detected)
        self.monitor_thread.start()
    
    def start_connect_monitoring(self):
        """Start monitoring for device connection"""
        if self.monitor_thread:
            self.monitor_thread.stop()
            self.monitor_thread.wait()
        
        self.monitor_thread = USBMonitorThread(self.first_capture, 'connect')
        self.monitor_thread.device_change_detected.connect(self.on_connect_detected)
        self.monitor_thread.start()
    
    def on_disconnect_detected(self, current_devices):
        """Handle device disconnection detection"""
        self.second_capture = current_devices
        self.workflow_status.setText("Device disconnected! Analyzing...")
        self.analyze_disconnect_difference()
    
    def on_connect_detected(self, current_devices):
        """Handle device connection detection"""
        self.second_capture = current_devices
        self.workflow_status.setText("Device connected! Analyzing...")
        self.analyze_connect_difference()
    
    def capture_after_disconnect(self):
        """Capture USB state after device disconnection"""
        self.capture_thread = USBCaptureThread()
        self.capture_thread.finished.connect(self.second_capture_disconnect_complete)
        self.capture_thread.start()
    
    def capture_after_connect(self):
        """Capture USB state after device connection"""
        self.capture_thread = USBCaptureThread()
        self.capture_thread.finished.connect(self.second_capture_connect_complete)
        self.capture_thread.start()
    
    def second_capture_disconnect_complete(self, devices):
        """Handle completion of second capture in disconnect workflow"""
        self.second_capture = devices
        self.analyze_disconnect_difference()
    
    def second_capture_connect_complete(self, devices):
        """Handle completion of second capture in connect workflow"""
        self.second_capture = devices
        self.analyze_connect_difference()
    
    def start_pre_disconnect_analysis(self):
        """Start detailed analysis before disconnection"""
        self.workflow_status.setText("Capturing detailed hardware information...")
        
        # We'll analyze the device after we identify it in the disconnect workflow
        # For now, proceed to countdown for disconnection
        QTimer.singleShot(2000, self.start_disconnect_countdown)
    
    def start_disconnect_countdown(self):
        """Start countdown for device disconnection"""
        self.workflow_status.setText("Now, when the countdown reaches zero, disconnect the device.")
        self.countdown_label.show()
        
        # Show disconnect image on the left
        self.hide_all_workflow_images()
        self.show_floating_image('disconnect', 'left')
        
        # Start countdown
        self.countdown_thread = CountdownThread(3)
        self.countdown_thread.countdown_update.connect(self.update_countdown)
        self.countdown_thread.countdown_finished.connect(self.countdown_finished_connected)
        self.countdown_thread.start()
    
    def analyze_disconnect_difference(self):
        """Analyze difference when device was disconnected"""
        # Find device that was removed
        removed_devices = self.get_devices_difference(self.second_capture, self.first_capture)
        
        if removed_devices:
            self.identified_device = removed_devices[0]  # Take first identified device
            # Start detailed inspection of the identified device using first_capture data
            self.start_detailed_inspection_for_identified_device()
        else:
            self.show_success("No device changes detected")
    
    def analyze_connect_difference(self):
        """Analyze difference when device was connected"""
        # Find device that was added
        added_devices = self.get_devices_difference(self.first_capture, self.second_capture)
        
        if added_devices:
            self.identified_device = added_devices[0]  # Take first identified device
            # Start detailed inspection of the newly connected device
            self.start_detailed_inspection_for_identified_device()
        else:
            self.show_success("No device changes detected")
    
    def start_detailed_inspection_for_identified_device(self):
        """Start detailed inspection for the identified device"""
        if self.identified_device:
            self.workflow_status.setText("Performing detailed hardware inspection...")
            self.inspection_thread = DetailedInspectionThread(self.identified_device)
            self.inspection_thread.inspection_complete.connect(self.detailed_inspection_complete)
            self.inspection_thread.start()
        else:
            self.show_success("Device identified but detailed inspection failed")
    
    def detailed_inspection_complete(self, inspection_data):
        """Handle completion of detailed inspection"""
        self.detailed_inspection_data = inspection_data
        self.show_success(f"Device captured: 1 device identified with detailed analysis")
    
    def get_devices_difference(self, before: List[USBDevice], after: List[USBDevice]) -> List[USBDevice]:
        """Find devices that are in 'after' but not in 'before'."""
        before_set = {(d.vendor_id, d.product_id, d.description) for d in before}
        return [d for d in after if (d.vendor_id, d.product_id, d.description) not in before_set]
    
    def show_success(self, message):
        """Show success message with checkmark"""
        self.workflow_status.hide()
        self.success_message.setText(message)
        self.success_frame.show()
        self.view_results_btn.show()
    
    def show_results(self):
        """Switch to results screen and display device information"""
        self.stacked_widget.setCurrentIndex(3)  # Switch to results screen
        self.display_device_results()
    
    def show_welcome(self):
        """Return to welcome screen"""
        self.stacked_widget.setCurrentIndex(1)
        self.reset_workflow_state()
    
    def restart_app(self):
        """Restart the application"""
        self.show_welcome()
    
    def reset_workflow_state(self):
        """Reset all workflow state"""
        # Stop any running monitor thread
        if self.monitor_thread:
            self.monitor_thread.stop()
            self.monitor_thread.wait()
            self.monitor_thread = None
            
        self.first_capture = []
        self.second_capture = []
        self.identified_device = None
        self.detailed_inspection_data = None
        self.workflow_status.show()
        self.countdown_label.show()
        self.success_frame.hide()
        self.view_results_btn.hide()
        
        # Clear device cards
        while self.device_cards_layout.count():
            child = self.device_cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    def display_device_results(self):
        """Display the identified device in big cards with copy buttons"""
        # Clear existing cards
        while self.device_cards_layout.count():
            child = self.device_cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        if not self.identified_device:
            no_device_label = QLabel("No device was identified")
            no_device_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_device_label.setFont(QFont("Arial", 16))
            no_device_label.setStyleSheet("color: #757575; padding: 40px;")
            self.device_cards_layout.addWidget(no_device_label)
            return
        
        device = self.identified_device
        
        # Device Name Card
        name_card = self.create_info_card("Name", device.description, "#4CAF50")
        self.device_cards_layout.addWidget(name_card)
        
        # USB Bus Card
        bus_card = self.create_info_card("USB Bus", f"Bus {device.bus}", "#2196F3")
        self.device_cards_layout.addWidget(bus_card)
        
        # Vendor ID Card
        vendor_card = self.create_info_card("Vendor ID", device.vendor_id, "#FF9800")
        self.device_cards_layout.addWidget(vendor_card)
        
        # Product ID Card
        product_card = self.create_info_card("Product ID", device.product_id, "#9C27B0")
        self.device_cards_layout.addWidget(product_card)
        
        # Plain text line
        plain_text = f"Bus {device.bus} Device {device.device}: ID {device.vendor_id}:{device.product_id} {device.description}"
        plain_card = self.create_info_card("Plain Text Line", plain_text, "#795548")
        self.device_cards_layout.addWidget(plain_card)
        
        # Add detailed inspection section if available
        if self.detailed_inspection_data:
            self.add_detailed_inspection_section()
    
    def create_info_card(self, title, value, color):
        """Create a big card for device information with copy button"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 3px solid {color};
                border-radius: 12px;
                padding: 20px;
                margin: 10px;
            }}
        """)
        
        layout = QVBoxLayout(card)
        
        # Title
        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {color}; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # Value
        value_label = QLabel(value)
        value_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        value_label.setStyleSheet("color: #212121; margin-bottom: 15px;")
        value_label.setWordWrap(True)
        layout.addWidget(value_label)
        
        # Copy button
        copy_btn = QPushButton("📋 Copy to Clipboard")
        copy_btn.clicked.connect(lambda: self.copy_to_clipboard(value))
        copy_btn.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        copy_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
            }}
            QPushButton:hover {{
                background-color: {self.darken_color(color)};
            }}
        """)
        layout.addWidget(copy_btn)
        
        return card
    
    def copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        
        # Show temporary feedback
        sender = self.sender()
        original_text = sender.text()
        sender.setText("✅ Copied!")
        QTimer.singleShot(1500, lambda: sender.setText(original_text))
    
    def darken_color(self, color):
        """Darken a hex color for hover effects"""
        color_map = {
            "#4CAF50": "#45a049",
            "#2196F3": "#1976D2", 
            "#FF9800": "#F57C00",
            "#9C27B0": "#7B1FA2",
            "#795548": "#5D4037"
        }
        return color_map.get(color, color)
    
    def add_detailed_inspection_section(self):
        """Add detailed inspection results directly to the results screen"""
        # Section header
        inspection_header = QLabel("🔍 Detailed Hardware Inspection")
        inspection_header.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        inspection_header.setStyleSheet("color: #607D8B; margin: 30px 0 20px 0; padding: 10px;")
        inspection_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.device_cards_layout.addWidget(inspection_header)
        
        # Detailed inspection text area
        inspection_text = QTextEdit()
        inspection_text.setFont(QFont("Courier", 9))
        inspection_text.setReadOnly(True)
        inspection_text.setText(self.detailed_inspection_data)
        inspection_text.setMinimumHeight(400)
        inspection_text.setMaximumHeight(500)
        inspection_text.setStyleSheet("""
            QTextEdit {
                background-color: #F5F5F5;
                border: 2px solid #607D8B;
                border-radius: 8px;
                padding: 15px;
                margin: 10px;
            }
        """)
        self.device_cards_layout.addWidget(inspection_text)
        
        # Copy detailed inspection button
        copy_inspection_btn = QPushButton("📋 Copy Detailed Inspection")
        copy_inspection_btn.clicked.connect(lambda: self.copy_to_clipboard(self.detailed_inspection_data))
        copy_inspection_btn.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        copy_inspection_btn.setStyleSheet("""
            QPushButton {
                background-color: #607D8B;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                margin: 10px;
            }
            QPushButton:hover {
                background-color: #455A64;
            }
        """)
        self.device_cards_layout.addWidget(copy_inspection_btn)

class DetailedInspectionThread(QThread):
    inspection_complete = pyqtSignal(str)
    
    def __init__(self, device):
        super().__init__()
        self.device = device
    
    def run(self):
        """Perform detailed hardware inspection"""
        result = self.get_detailed_device_info()
        self.inspection_complete.emit(result)
    
    def get_detailed_device_info(self):
        """Get detailed device information using lsusb -v and udevadm"""
        info_sections = []
        
        # Basic device info
        info_sections.append("=== BASIC DEVICE INFORMATION ===")
        info_sections.append(f"Device Name: {self.device.description}")
        info_sections.append(f"USB Bus: {self.device.bus}")
        info_sections.append(f"Device Number: {self.device.device}")
        info_sections.append(f"Vendor ID: {self.device.vendor_id}")
        info_sections.append(f"Product ID: {self.device.product_id}")
        info_sections.append("")
        
        # Detailed lsusb output
        info_sections.append("=== DETAILED USB INFORMATION (lsusb -v) ===")
        try:
            # Run lsusb -v for this specific device
            result = subprocess.run([
                'lsusb', '-v', '-d', f"{self.device.vendor_id}:{self.device.product_id}"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout:
                info_sections.append(result.stdout)
            else:
                info_sections.append("Could not retrieve detailed USB information")
                if result.stderr:
                    info_sections.append(f"Error: {result.stderr}")
        except subprocess.TimeoutExpired:
            info_sections.append("Timeout while retrieving detailed USB information")
        except Exception as e:
            info_sections.append(f"Error running lsusb: {e}")
        
        info_sections.append("")
        
        # udevadm information
        info_sections.append("=== SYSTEM DEVICE INFORMATION (udevadm) ===")
        try:
            # Find the device path using udevadm
            result = subprocess.run([
                'find', '/sys/bus/usb/devices/', '-name', f"{self.device.bus}-*"
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0 and result.stdout:
                device_paths = result.stdout.strip().split('\n')
                for path in device_paths:
                    if path:
                        # Get udevadm info for this path
                        udev_result = subprocess.run([
                            'udevadm', 'info', '--path', path
                        ], capture_output=True, text=True, timeout=5)
                        
                        if udev_result.returncode == 0:
                            info_sections.append(f"Device path: {path}")
                            info_sections.append(udev_result.stdout)
                            break
            else:
                info_sections.append("Could not find device in sysfs")
        except Exception as e:
            info_sections.append(f"Error running udevadm: {e}")
        
        return "\n".join(info_sections)

def main():
    app = QApplication(sys.argv)
    
    try:
        window = WhichUSBGUI()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"GUI Error: {e}")
        print("This might be due to:")
        print("1. Missing GUI libraries")
        print("2. Display issues")
        print("3. Permission problems")
        print("\nTry running the command-line version instead: ./cli/which-usb")
        sys.exit(1)

if __name__ == "__main__":
    main()

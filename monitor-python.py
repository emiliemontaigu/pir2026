#!/usr/bin/env python3

"""Monitor-python : a monitor tool for robot control, using QT5
Usage: monitor-python.py

"""

import os
import time
import sys

from PyQt5 import (QtCore, QtWidgets, QtGui)

from image_recognition import CameraThread
from main_window import Ui_MainWindow
from log_dialog import Ui_Dialog
from globvar import GlobVar
from network_2Xbee import Robot

import base64

__author__ = "Sebastien DI MERCURIO"
__copyright__ = "Copyright 2024, INSA Toulouse"
__credits__ = ["Sebastien DI MERCURIO"]
__license__ = "GPL"
__version__ = "1.1"
__maintainer__ = "Sebastien DI MERCURIO"
__email__ = "dimercur@insa-toulouse.fr"
__status__ = "Production"

"""
The main application class.

Instantiate it for opening main window 
"""

# --- Add this at the top ---
# class CameraApp(QtCore.QThread):
#     image_update = QtCore.pyqtSignal(QtGui.QImage)

#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self._running = False
#         self.cap = None

#     def run(self):
#         self.cap = cv2.VideoCapture(0)
#         if not self.cap.isOpened():
#             print("Error: Cannot open camera")
#             return

#         prev_time = 0
#         while self._running:
#             ret, frame = self.cap.read()
#             if not ret:
#                 continue

#             # --- image processing ---
#             gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
#             blur = cv2.GaussianBlur(gray, (5, 5), 0)
#             edges = cv2.Canny(blur, 50, 150)
#             contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
#             for cnt in contours:
#                 approx = cv2.approxPolyDP(cnt, 0.02 * cv2.arcLength(cnt, True), True)
#                 if len(approx) == 4 and cv2.contourArea(cnt) > 10000:
#                     cv2.drawContours(frame, [approx], -1, (0, 255, 0), 3)

#             # --- FPS ---
#             curr_time = time.time()
#             fps = 1 / (curr_time - prev_time) if prev_time != 0 else 0
#             prev_time = curr_time
#             cv2.putText(frame, f"FPS: {int(fps)}", (10, 30),
#                         cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)

#             # --- convert to QImage ---
#             rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#             h, w, ch = rgb_image.shape
#             bytes_per_line = ch * w
#             qt_image = QtGui.QImage(rgb_image.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)

#             # --- emit signal ---
#             self.image_update.emit(qt_image)

#         self.cap.release()

#     def start_camera(self):
#         if not self._running:
#             self._running = True
#             self.start()

#     def stop_camera(self):
#         self._running = False
        # self.wait()

class Window(QtWidgets.QMainWindow, Ui_MainWindow):
    _msg_dialog = None
    _batteryTimer = None
    _FPSTimer = None
    
    fps = 0
    robot = None    # Robot serial instance

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
                
        self._msg_dialog = QtWidgets.QDialog()
        self._msg_dialog.ui = Ui_Dialog()
        self._msg_dialog.ui.setupUi(self._msg_dialog)
        
        self.fps = 0
        self.robot = Robot()        # instantiate but don't open yet

        self.networkThread = Robot()
        #self.image = CameraThread()
        # Start network thread
        #self.networkThread.start()
        
        # Create battery timer
        #self._batteryTimer = QtCore.QTimer()
        #self._batteryTimer.timeout.connect(self.OnBatteryTimeout)
        
        # Create fps timer
        #self._FPSTimer = QtCore.QTimer()
        #self._FPSTimer.timeout.connect(self.OnFPSTimeout)

        self.EnableUIWidgets("Network")
        self.DisableUIWidgets("Robot")

        self.connectSignalSlots()

    # ------------------------------------------------------------------ #
    #  Robot initialisation (delegates to Robot class)                    #
    # ------------------------------------------------------------------ #

    def init_robot(self) -> bool:
        """Open serial port and run the robot boot sequence."""
        if not self.robot.open():
            QtWidgets.QMessageBox.critical(
                self, "Serial error",
                f"Cannot open serial port.\nCheck the cable and port configuration."
            )
            return False

        if not self.robot.init():
            QtWidgets.QMessageBox.critical(
                self, "Robot not ready",
                "Robot did not respond to PING after init.\nCheck connection and power."
            )
            self.robot.close()
            return False

        return True
        
    def connectSignalSlots(self):
        # Buttons
        self.pushButton_start.pressed.connect(self.OnButtonPress_Start)
        self.pushButton_confirmArena.pressed.connect(self.OnButtonPress_ConfirmArena)
        self.pushButton_up.pressed.connect(self.OnButtonPress_Up)
        self.pushButton_down.pressed.connect(self.OnButtonPress_Down)
        self.pushButton_stop.pressed.connect(self.OnButtonPress_Stop)
        self.pushButton_left.pressed.connect(self.OnButtonPress_Left)
        self.pushButton_right.pressed.connect(self.OnButtonPress_Right)
        
        # Checkbox
        self.checkBox_enableCamera.stateChanged.connect(self.OnCheckBoxChanged_EnableCamera)
        self.checkBox_enableFPS.stateChanged.connect(self.OnCheckBoxChanged_EnableFPS)
        self.checkBox_enablePosition.stateChanged.connect(self.OnCheckBoxChanged_EnablePosition)
        self.checkBox_getBattery.stateChanged.connect(self.OnCheckBoxChanged_GetBattery)
        
        # Menu
        self.action_OpenMessageLog.triggered.connect(self.OnMenu_OpenMessageLog)
        self.action_Quitter.triggered.connect(self.OnMenu_Quitter)
        
        # Message Dialog
        self._msg_dialog.ui.pushButton_clearLog.pressed.connect(self.OnButtonPress_ClearLog)
        self._msg_dialog.ui.pushButton_closeLog.pressed.connect(self.OnButtonPress_CloseLog)
        
        # Network signals
        #self.networkThread.receptionEvent.connect(self.OnReceptionEvent)
        #self.networkThread.connectionEvent.connect(self.OnConnectionEvent)
        #self.networkThread.logEvent.connect(self.OnLogEvent)
        #self.networkThread.answerEvent.connect(self.OnAnswerEvent)
    
    def EnableUIWidgets(self, area):
        if area == "Network":
            self.checkBox_watchdog.setDisabled(False)
            self.pushButton_start.setDisabled(False)
            self.label_Image.setDisabled(False)
            self.pushButton_confirmArena.setDisabled(False)
            self.checkBox_enableCamera.setDisabled(False)
            self.checkBox_enableFPS.setDisabled(False)
            self.checkBox_enablePosition.setDisabled(False)
            self.label_RobotID.setDisabled(False)
            self.label_RobotAngle.setDisabled(False)
            self.label_RobotPos.setDisabled(False)
            self.label_RobotDirection.setDisabled(False)
        else:  # area Robot
            self.groupBox_mouvments.setDisabled(False)
            self.groupBox_AnswerandBattery.setDisabled(False)
                      
    def DisableUIWidgets(self, area):
        if area == "Network":
            self.checkBox_watchdog.setDisabled(True)
            self.pushButton_start.setDisabled(True)
            self.label_Image.setDisabled(True)
            self.pushButton_confirmArena.setDisabled(True)
            self.checkBox_enableCamera.setDisabled(True)
            self.checkBox_enableFPS.setDisabled(True)
            self.checkBox_enablePosition.setDisabled(True)
            self.label_RobotID.setDisabled(True)
            self.label_RobotAngle.setDisabled(True)
            self.label_RobotPos.setDisabled(True)
            self.label_RobotDirection.setDisabled(True)
        else:  # area Robot
            self.groupBox_mouvments.setDisabled(True)
            self.groupBox_AnswerandBattery.setDisabled(True)

    @QtCore.pyqtSlot() 
    def OnButtonPress_Start(self):
        if self.pushButton_start.text() == "Start r&obot":
            # Initialise the serial link and boot the robot
            if self.init_robot():
                self.pushButton_start.setText("Reset r&obot")
                self.EnableUIWidgets("Robot")
        else:
            # Reset: close serial port and disable robot widgets
            self.robot.close()
            self.pushButton_start.setText("Start r&obot")
            self.DisableUIWidgets("Robot")
            
    @QtCore.pyqtSlot() 
    def OnButtonPress_ConfirmArena(self):
        self.networkThread.cameraAskArena()
        msg = QtWidgets.QMessageBox
        ret = msg.question(self, '', 'Arena boundaries are correctly detected ?', msg.Yes | msg.No)
        
        if ret == msg.Yes:
            self.networkThread.cameraConfirmArena()
        else:
            self.networkThread.cameraInfirmArena()
        
    @QtCore.pyqtSlot() 
    def OnButtonPress_Up(self):
        self.networkThread.move(100)
      
    @QtCore.pyqtSlot()   
    def OnButtonPress_Down(self):
        self.networkThread.move(-100)
    
    @QtCore.pyqtSlot() 
    def OnButtonPress_Stop(self):
        self.networkThread.move(0)
     
    @QtCore.pyqtSlot() 
    def OnButtonPress_Left(self):
        self.networkThread.turn(100)
     
    @QtCore.pyqtSlot() 
    def OnButtonPress_Right(self):
        self.networkThread.turn(-100)
      
    @QtCore.pyqtSlot(int)  
    def OnCheckBoxChanged_EnableCamera(self, state):
        if self.checkBox_enableCamera.isChecked():
            self.networkThread.cameraOpen()
        else:
            self.networkThread.cameraClose()
        
    @QtCore.pyqtSlot(int) 
    def OnCheckBoxChanged_EnableFPS(self, state):
        if state != 0:
            self._FPSTimer.start(1000)
            self.checkBox_enableFPS.setText("FPS (0)")
        else:
            self._FPSTimer.stop()
            self.checkBox_enableFPS.setText("Enable FPS")
        
    @QtCore.pyqtSlot(int) 
    def OnCheckBoxChanged_EnablePosition(self, state):
        if self.checkBox_enablePosition.isChecked():
            self.networkThread.cameraGetPosition()
        else:
            self.networkThread.cameraStopPosition()
        
    @QtCore.pyqtSlot(int) 
    def OnCheckBoxChanged_GetBattery(self, state):
        if state != 0:
            self._batteryTimer.start(5000)
        else:
            self._batteryTimer.stop()
        
    @QtCore.pyqtSlot() 
    def OnMenu_OpenMessageLog(self):
        self._msg_dialog.show()
       
    @QtCore.pyqtSlot()  
    def OnMenu_Quitter(self):
        self._msg_dialog.hide()
        self.close()
          
    def closeEvent(self, event):
        self._msg_dialog.hide()
        self.robot.close()
        event.accept()
          
    @QtCore.pyqtSlot() 
    def OnButtonPress_ClearLog(self):
        plainTextEdit = self._msg_dialog.ui.plainTextEdit
        plainTextEdit.document().clear()
        
    @QtCore.pyqtSlot() 
    def OnButtonPress_CloseLog(self):
        self._msg_dialog.hide()
              
    @QtCore.pyqtSlot() 
    def OnBatteryTimeout(self) -> None:
        self.networkThread.robotGetBattery()
    
    @QtCore.pyqtSlot() 
    def OnFPSTimeout(self) -> None:
        self.checkBox_enableFPS.setText("FPS (" + str(self.fps) + ")")
        self.fps = 0
        
    # @QtCore.pyqtSlot(int) 
    # def OnConnectionEvent(self, event) -> None:       
    #     if event == NetworkEvents.EVENT_CONNECTED:
    #         GlobVar.connectedToPi = True
    #         print("Connected to server")
    #     elif event == NetworkEvents.EVENT_CONNECTION_LOST:
    #         GlobVar.connectedToPi = False
    #         print("Disconnected from server")
    #         self.pushButton_start.setText("Start r&obot")
    #         self.DisableUIWidgets("Robot")
            
    @QtCore.pyqtSlot(int) 
    def OnAnswerEvent(self, ans) -> None:
        if ans == NetworkAnswers.ACK:
            self.label_lastAnswer.setText("Acknowledged (AACK)")
        elif ans == NetworkAnswers.NACK:
            self.label_lastAnswer.setText("Not acknowledged (ANAK)")
        elif ans == NetworkAnswers.COM_ERROR:
            self.label_lastAnswer.setText("Command error (ACER)")
        elif ans == NetworkAnswers.TIMEOUT_ERROR:
            self.label_lastAnswer.setText("Timeout - no answer")
        elif ans == NetworkAnswers.CMD_REJECTED:
            self.label_lastAnswer.setText("Command rejected (ACRJ)")
        else:
            self.label_lastAnswer.setText("Unknown answer")
    
    @QtCore.pyqtSlot(str) 
    def OnLogEvent(self, txt) -> None:
        self._msg_dialog.ui.plainTextEdit.textCursor().insertText(txt)
    

try:     
    if len(sys.argv) >= 3:
        GlobVar.port = int(sys.argv[2])
        
    app = QtWidgets.QApplication(sys.argv)
    window = Window()
    window.show()
    app.exec_()
    
except KeyboardInterrupt:
    print("Bye bye")
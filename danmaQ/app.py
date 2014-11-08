#!/usr/bin/env python2
# -*- coding:utf-8 -*-
import sys
import json
import requests
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import pyqtSignal
from .danmaq_ui import Danmaku
from .tray_icon import DanmaQTrayIcon, ICON_ENABLED
from .settings import load_config, save_config
from .config_dialog import ConfigDialog


class SubscribeThread(QtCore.QThread):
    new_danmaku = pyqtSignal(str, str, str, name="newDanmaku")

    def __init__(self, server, channel, passwd, parent=None):
        super(SubscribeThread, self).__init__(parent)
        self.server = server
        self.channel = channel
        self.passwd = passwd

    def run(self):
        uri = "/api/v1/channels/{cname}/danmaku".format(cname=self.channel)
        if uri.startswith("/") and self.server.endswith("/"):
            server = self.server[:-1]
        else:
            server = self.server
        url = server + uri

        while 1:
            try:
                res = requests.get(
                    url, headers={"X-GDANMAKU-AUTH-KEY": self.passwd})
            except requests.exceptions.ConnectionError:
                continue
            if res.status_code == 200 and res.text:
                try:
                    dm_opts = json.loads(res.text)
                except:
                    continue
                else:
                    for dm in dm_opts:
                        self.new_danmaku.emit(
                            dm['text'], dm['style'], dm['position'])

    def __del__(self):
        self.wait()


class DanmakuApp(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(DanmakuApp, self).__init__(parent)
        self.setWindowTitle("Danmaku")
        self.setWindowIcon(QtGui.QIcon(ICON_ENABLED))

        self.trayIcon = DanmaQTrayIcon(self)
        self.trayIcon.show()
        self.config_dialog = ConfigDialog(self)
        self._options = load_config()

        layout = QtWidgets.QVBoxLayout()
        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(QtWidgets.QLabel("Server: ", self))
        self._server = QtWidgets.QLineEdit(
            self._options['http_stream_server'], self)
        hbox.addWidget(self._server)
        layout.addLayout(hbox)

        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(QtWidgets.QLabel("Save As Default Server: ", self))
        self._save_server = QtWidgets.QCheckBox(self)
        hbox.addWidget(self._save_server)
        layout.addLayout(hbox)

        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(QtWidgets.QLabel("Channel: ", self))
        self._chan = QtWidgets.QLineEdit("demo", self)
        hbox.addWidget(self._chan)
        layout.addLayout(hbox)

        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(QtWidgets.QLabel("Password: ", self))
        self._passwd = QtWidgets.QLineEdit("", self)
        hbox.addWidget(self._passwd)
        layout.addLayout(hbox)

        hbox = QtWidgets.QHBoxLayout()
        self.hide_button = QtWidgets.QPushButton("Hide", self)
        self.main_button = QtWidgets.QPushButton("Subscribe", self)
        hbox.addWidget(self.hide_button)
        hbox.addWidget(self.main_button)
        layout.addLayout(hbox)
        self.setLayout(layout)

        self.hide_button.released.connect(self.hide)
        self.main_button.released.connect(self.subscribe_danmaku)
        self.config_dialog.preferenceChanged.connect(self.apply_new_preference)
        self.trayIcon.toggleAction.triggered.connect(self.subscribe_danmaku)
        self.trayIcon.exitAction.triggered.connect(self.close)
        self.trayIcon.showAction.triggered.connect(self.show)
        self.trayIcon.configAction.triggered.connect(self.config_dialog.show)

        self.workThread = None
        self.dms = {}

    def subscribe_danmaku(self):
        if self.workThread is None or self.workThread.isFinished():
            self.workThread = SubscribeThread(
                self._server.text(),
                self._chan.text(),
                self._passwd.text(),
                parent=self,
            )
            self.workThread.started.connect(self.on_subscription_started)
            self.workThread.finished.connect(self.on_subscription_finished)
            self.workThread.start()
            self.workThread.new_danmaku.connect(self.on_new_danmaku)
            self.hide()
        else:
            self.workThread.terminate()

    def on_new_danmaku(self, text, style, position):
        dm = Danmaku(text, style=style, position=position)
        dm.exited.connect(self.delete_danmaku)
        self.dms[str(id(dm))] = dm

        dm.show()

    def delete_danmaku(self, _id):
        dm = self.dms.pop(_id)
        dm.close()

    def on_subscription_started(self):
        if self._save_server.isChecked():
            opts = load_config()
            opts['http_stream_server'] = self._server.text()
            save_config(opts)

        self.main_button.setText("Unsubscribe")
        self.trayIcon.set_icon_running()
        self.trayIcon.showMessage(
            "DanmaQ",
            "Subscribing danmaku from {}".format(self.workThread.server)
        )

    def on_subscription_finished(self):
        _dms = [dm for _, dm in self.dms.items()]
        for dm in _dms:
            dm.hide()
            dm.clean_close()
        self.trayIcon.set_icon_not_running()
        self.main_button.setText("Subscribe")
        self.trayIcon.showMessage("DanmaQ", "Subscription Finished")

    def apply_new_preference(self):
        pref = self.config_dialog.preferences()
        # print(pref)
        Danmaku.set_options(pref)


def main():
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    app = QtWidgets.QApplication(sys.argv)
    danmakuApp = DanmakuApp()
    danmakuApp.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
# vim: ts=4 sw=4 sts=4 expandtab

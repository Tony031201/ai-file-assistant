import os.path
import sys,json
from PyQt5.QtWidgets import QStackedWidget,QLabel,QApplication, QMainWindow,QHBoxLayout, QToolBar, QAction, QSplitter, QListWidget, QSizePolicy, QTextEdit, QLineEdit, QPushButton, QWidget, QVBoxLayout
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5 import QtGui, QtCore
from data.meta_data import DATA_DIR
from core.test_claud import ClaudClient
from core.memory_pipe import Memory_Pipe
from core.ai_parse import parse_response,merge_response
from sql.sql_filter import SQL_Filter
from sql.db_tools import DBTools
from analyse.analyse import analyze
from visualization.interface import visualization
from generate.create_file import createFile
from sql.tracker import start_watching,stop_watching, should_ignore,initialize
from core.error_handler import error
from sql.sync_rebuild import rebuild_files_table
import data.meta_data as meta_data

class AIWorker(QThread):
    # 线程类,用于AI输出
    finished = pyqtSignal(object)  # 定义信号，传递 AI 回复

    def __init__(self, user_text):
        super().__init__()
        self.user_text = user_text

    def run(self):
        reply = ClaudClient().send_message(messages=self.user_text)
        filter_reply = parse_response(reply)
        self.finished.emit(filter_reply)

class WatchThread(QThread):
    def run(self):
        rebuild_files_table(meta_data.get_watch_path(), should_ignore)
        start_watching()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # 记忆管道
        self.memory_pipe = Memory_Pipe(5)

        # 布局代码 #
        # 设置窗口标题和大小
        self.setWindowTitle("Assistant")
        self.resize(1000, 680)
        QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
        self.setWindowIcon(QtGui.QIcon("assets/robot.svg"))

        # 顶部工具栏：主题切换
        tb = QToolBar("Toolbar", self)
        tb.setMovable(False)
        self.addToolBar(QtCore.Qt.TopToolBarArea, tb)
        act_light = QAction("浅色", self)
        act_dark = QAction("深色", self)
        act_light.triggered.connect(lambda: self.apply_theme("light"))
        act_dark.triggered.connect(lambda: self.apply_theme("dark"))
        tb.addAction(act_light);
        tb.addAction(act_dark)

        # 左侧侧栏
        side = QListWidget()
        side.addItems(["会话", "设置", "API"])  # 占位
        side.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        side.setObjectName("SideList")

        # --- 页面1：会话 ---
        chat_page = QWidget()
        chat_layout = QVBoxLayout(chat_page)

        self.chat_area = QTextEdit(readOnly=True)
        self.chat_area.setObjectName("ChatArea")

        self.input_box = QLineEdit(placeholderText="请输入指令")
        self.input_box.setObjectName("InputBox")
        self.send_button = QPushButton("发送")
        self.send_button.setObjectName("PrimaryButton")
        self.send_button.clicked.connect(self.send_message)

        h = QHBoxLayout()
        h.addWidget(self.input_box, 1)
        h.addWidget(self.send_button)

        chat_layout.addWidget(self.chat_area)
        chat_layout.addLayout(h)

        # --- 页面2：设置 ---
        settings_page = QWidget()
        settings_layout = QVBoxLayout(settings_page)

        # 显示当前路径
        self.watch_path_label = QLabel(f"当前 WATCH_PATH: {meta_data.get_watch_path()}")

        # 输入新路径
        self.watch_path_edit = QLineEdit()
        self.watch_path_edit.setPlaceholderText("输入新的 WATCH_PATH")

        save_btn = QPushButton("保存")

        def save_path():
            new_path = self.watch_path_edit.text().strip()

            if not new_path:
                self.statusBar().showMessage("WATCH_PATH 为空")
                return
            if not os.path.isdir(new_path):
                self.statusBar().showMessage("路径不存在或不是目录")
                return

            # 重启监控
            print(f"修改前:{meta_data.get_watch_path()}")
            stop_watching()
            meta_data.set_watch_path(new_path)
            print(f"修改后:{meta_data.get_watch_path()}")
            initialize()
            start_watching()
            self.watch_path_label.setText(f"当前 WATCH_PATH: {meta_data.get_watch_path()}")
            self.statusBar().showMessage(f"WATCH_PATH 修改为: {meta_data.get_watch_path()}")

        save_btn.clicked.connect(save_path)

        settings_layout.addWidget(self.watch_path_label)
        settings_layout.addWidget(self.watch_path_edit)
        settings_layout.addWidget(save_btn)

        # --- 页面3：API ---
        api_page = QWidget()
        api_layout = QVBoxLayout(api_page)

        # 显示当前api
        self.api_label = QLabel(f"当前 API: {meta_data.get_api()}")

        # 输入新api
        self.api_edit = QLineEdit()
        self.api_edit.setPlaceholderText("输入新的 API")

        save_api_btn = QPushButton("保存API")

        def save_api():
            new_api = self.api_edit.text().strip()

            if not new_api:
                self.statusBar().showMessage("API 为空")
                return

            # 重启监控
            print(f"修改前:{meta_data.get_api()}")
            stop_watching()
            meta_data.set_api(new_api)
            print(f"修改后:{meta_data.get_api()}")
            initialize()
            start_watching()
            self.api_label.setText(f"当前 API: {meta_data.get_api()}")
            self.statusBar().showMessage(f"API 修改为: {meta_data.get_api()}")

        save_btn.clicked.connect(save_api)

        api_layout.addWidget(self.api_label)
        api_layout.addWidget(self.api_edit)
        api_layout.addWidget(save_api_btn)


        # --- 右侧堆叠页面 ---
        stacked = QStackedWidget()
        stacked.addWidget(chat_page)  # index 0
        stacked.addWidget(settings_page)  # index 1
        stacked.addWidget(api_page) # index 2

        # 绑定切换逻辑
        side.currentRowChanged.connect(stacked.setCurrentIndex)

        # --- 中央区：左右分隔 ---
        splitter = QSplitter()
        splitter.addWidget(side)
        splitter.addWidget(stacked)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        # 启动目录监控
        self.watch_thread = WatchThread()
        self.watch_thread.start()

    def closeEvent(self, event):
        # 窗口关闭时调用
        try:
            # 关闭监控
            stop_watching()
        except Exception as e:
            error("main.py","main.py",e)
        if hasattr(self, "watch_thread"):
            self.watch_thread.quit()
            self.watch_thread.wait()
        event.accept()


    def send_message(self):
        user_text = self.input_box.text().strip()
        self.memory_pipe.process({"role":"user","content":user_text})
        if user_text:
            # 显示用户输入
            self.chat_area.append(f"我: {user_text}")
            self.chat_area.append(f"助手: 等待中..")
            self.chat_area.append("") #空行分隔
            self.input_box.clear()

            # 模拟ai输出
            # 获取管道中的记忆
            pipe = self.memory_pipe.get_pipe()

            self.worker = AIWorker(json.dumps(pipe, ensure_ascii=False, indent=2))
            self.worker.finished.connect(self.display_reply)
            self.worker.start()

    def display_reply(self,filter_reply):
        # filter_reply为通过过滤器的信息

        # 合并信息后续并入记忆管道
        merge = merge_response(filter_reply)

        # print("查看目前的记忆管道:")
        # print(self.memory_pipe.get_pipe())

        ### 指令分流 ###
        sql_output = None
        analyze_output = None
        # 当指令是sql，意味着这条信息的目的是查询sql。并且有实际存在的sql语句
        if filter_reply["sql"] and filter_reply["instruction"].strip() == "sql":
            judge = SQL_Filter(filter_reply["sql"])
            if judge["status"]:
                # 合法sql,可以执行
                # 连接数据库, 执行sql
                db = DBTools()
                sql_output = db.custom_instruction(str(judge['sql']))
                db.close()
            else:
                # 未授权sql, 禁止执行
                pass
        elif filter_reply["instruction"].strip() == "analyse":
            # 当指令为analyse，意味着这条信息的目的是代码分析，需要调动代码分析模块
            self.chat_area.append("调用分析模块...")
            analyze_output = analyze(purpose=filter_reply["answer"].strip(),file_path=filter_reply["file_path"])
        elif filter_reply["instruction"].strip() == "visualization":
            # 当指令为visualization，意味着这条信息的目的是数据可视化，需要调动可视化模块
            self.chat_area.append("调用数据可视化模块")
            if visualization(file_path=filter_reply["file_path"]):
                self.chat_area.append("图像生成成功")
            else:
                self.chat_area.append("图像生成失败, 请查看该文件是否为csv文件")
        elif filter_reply["instruction"].strip() == "generation":
            # 当指令为generation，意味着这条信息的目的是文件生成，需要调动文件创建模块
            self.chat_area.append("调用文件创建模块")
            if createFile(file_path=filter_reply["file_path"],content=filter_reply["file_content"]):
                self.chat_area.append("文件生成成功")
            else:
                self.chat_area.append("文件生成失败，请查看目录是否存在，或者同名文件已经存在")
        elif filter_reply["instruction"].strip() == "无":
            # 当指令为无，意味着用户的目的是咨询信息，不需要调用任何模块
            pass

        output = "回答: " + filter_reply["answer"]
        self.chat_area.append(output)
        sql_input = SQL_Filter(filter_reply['sql'])['sql']
        if sql_output:
            self.chat_area.append(f"执行sql:{sql_input}")
            self.chat_area.append("执行结果:")
            for out in sql_output:
                self.chat_area.append(str(out))
            # 将sql执行的结果塞进记忆管道
            self.memory_pipe.process({"role": "reply", "content": merge + " 执行结果:" + str(sql_output)})
        elif sql_input:
            self.chat_area.append(f"执行sql:{sql_input}")
            self.chat_area.append("数据库中没有相关记录")

        if analyze_output:
            self.chat_area.append("分析结果:")
            self.chat_area.append(analyze_output)
            # 将分析的结果塞进记忆管道
            self.memory_pipe.process({"role": "reply", "content": merge + " 分析结果:" + str(analyze_output)})
        else:
            self.memory_pipe.process({"role": "reply", "content": merge})
        self.chat_area.append("")

    def load_qss(self,path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

    def apply_theme(self, mode="light"):
        qss = self.load_qss(os.path.join(DATA_DIR,"style.css"))
        self.setStyleSheet(qss)



if __name__ == '__main__':
    app = QApplication(sys.argv)    # 创建应用对象
    window = MainWindow()   # 创建窗口对象
    window.show()   # 显示窗口
    sys.exit(app.exec_())   # 启动事件循环
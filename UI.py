from tkinter import *
from tkinter.messagebox import *
from tkinter.filedialog import *
from ttkbootstrap import Style
import tkinter.ttk as ttk
from multiprocessing import Pipe
from PIL import Image, ImageTk
from threading import Thread
import pathlib
import fitz
import re

class UI:
    def __init__(self, width, height, pipe: Pipe()[0]):
        self.width = width
        self.height = height
        self.dirDict = {}
        self.pipe = pipe
        
        # ttkbootstrap 风格美化
        style = Style(theme='sandstone')
        self.root = style.master
        self.root.title('Comicor')

        # 初始化
        self.init_button()
        self.init_view()

    def init_button(self):
        # 按钮框架
        buttonFrame = Frame(self.root)
        buttonFrame.pack(pady=15)

        ttk.Button(buttonFrame, text='文件夹', width=10, command=self.open).grid(row=1, column=1, padx=15, pady=5)
        ttk.Button(buttonFrame, text='提取图片', width=10, command=self.divide).grid(row=1, column=2, padx=15, pady=5)
        ttk.Button(buttonFrame, text='超分图片', width=10, command=self.rdn).grid(row=1, column=3, padx=15, pady=5)
        ttk.Button(buttonFrame, text='修改尺寸', width=10, command=self.resize).grid(row=1, column=4, padx=15, pady=5)

        ttk.Button(buttonFrame, text='清空', width=10, command=self.clear).grid(row=2, column=1, padx=15, pady=5)
        ttk.Button(buttonFrame, text='合并为 PDF', width=10, command=self.merge).grid(row=2, column=2, padx=15, pady=5)
        ttk.Button(buttonFrame, text='合并为长图', width=10, command=self.long).grid(row=2, column=3, padx=15, pady=5)
        ttk.Button(buttonFrame, text='压缩图片', width=10, command=self.compress).grid(row=2, column=4, padx=15, pady=5)

        ttk.Button(buttonFrame, text='转 PNG', width=10, command=self.to_PNG).grid(row=3, column=2, padx=15, pady=5)
        ttk.Button(buttonFrame, text='转 JPG', width=10, command=self.to_JPG).grid(row=3, column=3, padx=15, pady=5)
        ttk.Button(buttonFrame, text='转 WEBP', width=10, command=self.to_WEBP).grid(row=3, column=4, padx=15, pady=5)

        # 图片公共尺寸
        Label(buttonFrame, text='宽', width=5).grid(row=1, column=5, padx=10)
        Label(buttonFrame, text='高', width=5).grid(row=1, column=7, padx=10)
        self.commomWidth = StringVar()
        self.commomHeight = StringVar()
        self.commomWidth.set(640)
        self.commomHeight.set(640)
        ttk.Entry(buttonFrame, textvariable=self.commomWidth, width=5).grid(row=1, column=6)
        ttk.Entry(buttonFrame, textvariable=self.commomHeight, width=5).grid(row=1, column=8)

        # 压缩率
        self.quality = StringVar()
        self.quality.set(50)
        Label(buttonFrame, text='压缩率').grid(row=2, column=5, padx=10)
        ttk.Entry(buttonFrame, textvariable=self.quality, width=5).grid(row=2, column=6)

        # 选中内容
        self.selectedPath = None
        self.selected = StringVar()
        self.selected.set('无')
        Label(buttonFrame, text='选中项').grid(row=3, column=5, padx=10)
        ttk.Label(buttonFrame, textvariable=self.selected, width=25).grid(row=3, columnspan=3, column=6)

    def init_view(self):
        # 列表框架
        listFrame = Frame(self.root)
        listFrame.pack()
        
        # 树状图
        self.treeView = ttk.Treeview(listFrame, show=["tree"])
        self.treeView["columns"] = ["column"]
        self.treeView.heading("column", text="Column")
        self.treeView.column("#0", width=40)
        self.treeView.column("#1", width=280)
        self.treeView.bind('<ButtonRelease-1>', self.update)
        self.treeView.pack(side=LEFT)

        # 设置滚动条
        sb = ttk.Scrollbar(listFrame)
        sb.pack(side=LEFT, fill=BOTH)

        sb.config(command=self.treeView.yview)

        # 画布
        self.image = None
        self.imgWidth = 360
        self.imgHeight = 180

        self.srcCanvas = Canvas(listFrame, width=self.imgWidth, height=self.imgHeight)
        self.srcCanvas.create_rectangle(0, 0, self.imgWidth - 1, self.imgHeight - 1, outline='gray')
        self.srcCanvas.create_text(self.imgWidth / 2, self.imgHeight / 2, text='图片预览', fill='gray')
        self.srcCanvas.pack(side=RIGHT, padx=15)

        # 进度条
        progFrame = Frame(self.root)
        progFrame.pack(pady=5)

        self.prog = ttk.Progressbar(progFrame, length=600)
        self.detail = Label(progFrame, text='')

    def tree(self, path, item):
        # 在目录后面加一个 . 只是为了防止目录名被识别为数字
        dirDict = {'parent': path, 'dirs': []}
        next = self.treeView.insert(item, "end", values=str(path.name + '.'))

        dirs = [f for f in path.iterdir() if f.is_dir()]
        files = [f for f in path.iterdir() if f.is_file()]

        # 设置排序元素
        key = lambda i: [[pair[0], int(pair[1])] for pair in re.findall('([^0-9]*)([0-9]+)', i.stem)]
        dirs = sorted(dirs, key=key)
        files = sorted(files, key=key)

        for d in dirs:
            dirDict['dirs'].append(self.tree(d, next))

        for f in files:
            self.treeView.insert(next, "end", values=str(f.name + '.'))

        return dirDict
    
    def recursion_dir(self, directory, dirDict, suffix):
        path = pathlib.Path(directory + '/' + dirDict['parent'].stem + suffix)
        if not path.exists():
            path.mkdir()
        self.data += ',' + str(dirDict['parent']) + ',' + str(path)

        dirs = dirDict['dirs']
        for d in dirs:
            self.recursion_dir(str(path), d, suffix)

    def recursion_merge_dir(self, directory, dirDict, suffix):
        path = pathlib.Path(directory + '/' + dirDict['parent'].stem + suffix)
        self.data += ',' + str(dirDict['parent']) + ',' + str(path)

        dirs = dirDict['dirs']
        for d in dirs:
            # 放到里面创建，这样就不会创建最后一层空目录
            if not path.exists():
                path.mkdir()

            self.recursion_merge_dir(str(path), d, suffix)

    def open(self):
        directory = askdirectory()
        if directory != '':
            # 删除原始数据
            self.clear()

            self.directory = pathlib.Path(directory)
            self.dirDict = self.tree(self.directory, '')

    def merge(self):
        # 排除空输入
        if self.dirDict == {}:
            return
        
        directory = askdirectory()
        if directory == '':
            return
        
        # 显示进度条
        self.prog['value'] = 0
        self.prog.pack(pady=10)
        self.detail.pack()

        # 构建数据并发送
        self.data = 'merge'
        self.recursion_merge_dir(directory, self.dirDict, '_merge')
        self.pipe.send(self.data)

    def long(self):
        if self.dirDict == {}:
            return
         
        directory = askdirectory()
        if directory == '':
            return
        
        # 显示进度条
        self.prog['value'] = 0
        self.prog.pack(pady=10)
        self.detail.pack()

        # 构建数据并发送
        self.data = 'long'
        self.recursion_merge_dir(directory, self.dirDict, '_long')
        self.pipe.send(self.data)

    def compress(self):
        if self.dirDict == {}:
            return
         
        directory = askdirectory()
        if directory == '':
            return

        if not self.quality.get().isdigit():
            showinfo('提示', '请输入一个 1~100 之间的数！')
            return
        
        # 显示进度条
        self.prog['value'] = 0
        self.prog.pack(pady=10)
        self.detail.pack()

        # 构建数据并发送
        self.data = 'compress' + ',' + self.quality.get()
        self.recursion_dir(directory, self.dirDict, '_compress')
        self.pipe.send(self.data)

    def resize(self):
        if self.dirDict == {}:
            return
         
        directory = askdirectory()
        if directory == '':
            return

        if not self.commomWidth.get().isdigit():
            showinfo('提示', '请输入一个数（宽度）！')
            return
        
        if not self.commomHeight.get().isdigit():
            showinfo('提示', '请输入一个数（高度）！')
            return
        
        # 显示进度条
        self.prog['value'] = 0
        self.prog.pack(pady=10)
        self.detail.pack()

        # 构建数据并发送
        self.data = 'resize' + ',' + self.commomWidth.get() + ',' + self.commomHeight.get()
        self.recursion_dir(directory, self.dirDict, '_resize-' + self.commomWidth.get() + 'x' + self.commomHeight.get())
        self.pipe.send(self.data)

    def rdn(self):
        # 排除空输入
        if self.dirDict == {}:
            return
         
        directory = askdirectory()
        if directory == '':
            return
        
        # 显示进度条
        self.prog['value'] = 0
        self.prog.pack(pady=10)
        self.detail.pack()

        # 构建数据并发送
        self.data = 'rdn'
        self.recursion_dir(directory, self.dirDict, '_rdn')
        self.pipe.send(self.data)

    def to_PNG(self):
        # 排除空输入
        if self.dirDict == {}:
            return
         
        directory = askdirectory()
        if directory == '':
            return
        
        # 显示进度条
        self.prog['value'] = 0
        self.prog.pack(pady=10)
        self.detail.pack()

        # 构建数据并发送
        self.data = 'png'
        self.recursion_dir(directory, self.dirDict, '_png')
        self.pipe.send(self.data)

    def to_JPG(self):
        # 排除空输入
        if self.dirDict == {}:
            return
         
        directory = askdirectory()
        if directory == '':
            return
        
        # 显示进度条
        self.prog['value'] = 0
        self.prog.pack(pady=10)
        self.detail.pack()

        # 构建数据并发送
        self.data = 'jpeg'
        self.recursion_dir(directory, self.dirDict, '_jpeg')
        self.pipe.send(self.data)

    def to_WEBP(self):
        # 排除空输入
        if self.dirDict == {}:
            return
         
        directory = askdirectory()
        if directory == '':
            return
        
        # 显示进度条
        self.prog['value'] = 0
        self.prog.pack(pady=10)
        self.detail.pack()

        # 构建数据并发送
        self.data = 'webp'
        self.recursion_dir(directory, self.dirDict, '_webp')
        self.pipe.send(self.data)

    def divide(self):
        directory = askdirectory()
        if directory == '':
            return
        
        if self.selectedPath == None or self.selectedPath.suffix != '.pdf':
            return

        # 显示进度条
        self.prog['value'] = 0
        self.prog.pack(pady=10)
        self.detail.pack()

        # 构建目录
        npath = pathlib.Path(directory + '/' + self.selectedPath.stem)
        npath.mkdir()

        # 构建数据并发送
        self.data = 'divide' + ',' + str(npath) + ',' + str(self.selectedPath)
        self.pipe.send(self.data)

    def clear(self):
        self.dirDict = {}
        self.selected.set('无')
        self.selectedPath = None

        # 删除预览
        if self.image:
            self.srcCanvas.delete(self.image)
            self.image = None

        # 删除原始数据
        data = self.treeView.get_children()
        if data != tuple():
            self.treeView.delete(data[0])

    def update(self, event):
        selectedItem = self.treeView.selection()
        self.selected.set('无')
        self.selectedPath = None
        
        if selectedItem:
            # 获得名称后，去掉末尾的 '.' ，还原目录名
            name = str(self.treeView.item(selectedItem[0])['values'][0][0:-1:1])
            suffix = name.split('.')[-1]

            # 回溯获取完整路径
            parent = self.treeView.parent(selectedItem)
            while parent:
                name = str(self.treeView.item(parent)['values'][0][0:-1:1]) + '\\' + name
                parent = self.treeView.parent(parent)

            # 设置选中内容
            self.selectedPath = pathlib.Path(str(self.directory.parent) + '\\' + name)
            self.selected.set(self.selectedPath.name)

            # 直接返回
            if suffix not in ['png', 'jpg', 'webp', 'jpeg']:
                if self.image:
                    self.srcCanvas.delete(self.image)
                    self.image = None
                return

            # 等比例缩放到合适的大小
            src = Image.open(str(self.selectedPath))
            ratio = min(self.imgWidth / src.width, self.imgHeight / src.height)
            width, height = int(src.width * ratio) - 5, int(src.height * ratio) - 5
            img = src.resize((width, height))

            self.commomWidth.set(str(src.width))
            self.commomHeight.set(str(src.height))

            # 注意一定要保存为成员变量，防止内存释放
            self.srcPhoto = ImageTk.PhotoImage(img)
            self.image = self.srcCanvas.create_image((self.imgWidth - width) / 2, (self.imgHeight - height) / 2, image=self.srcPhoto, anchor="nw")
        elif self.image:
            self.srcCanvas.delete(self.image)
            self.image = None

    # 接收数据并刷新
    def result(self):
        while True:
            data = self.pipe.recv().split(',')
            self.prog['value'] = max(self.prog['value'], 100 / int(data[1]) * int(data[0]))
            self.detail['text'] = '正在处理（剩余' + data[3] + '） '  + data[2]

    # 开启消息循环
    def run(self):
        # 设置窗口居中
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        x = int(screen_width / 2 - self.width / 2)
        y = int(screen_height / 2 - self.height / 2)
        size = '{}x{}+{}+{}'.format(self.width, self.height, x, y)

        # 启动刷新线程
        tr = Thread(target=self.result)
        tr.daemon = True
        tr.start()

        self.root.geometry(size)
        self.root.mainloop()

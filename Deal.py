from multiprocessing import Pipe
from concurrent.futures import ThreadPoolExecutor
from ISR.models import RDN
from io import BytesIO
from PIL import Image, ImageTk
from reportlab.lib.pagesizes import portrait
from reportlab.pdfgen import canvas
import numpy as np
import fitz
import pathlib
import re
import cv2

class Deal:
    def __init__(self, pipe: Pipe()[1]):
        self.pipe = pipe

    def run(self):
        self.model = RDN(weights='noise-cancel')

        while True:
            self.data = self.pipe.recv().split(',')
            if self.data[0] == 'merge':
                self.merge()
            elif self.data[0] == 'long':
                self.long()
            elif self.data[0] == 'compress':
                self.compress()
            elif self.data[0] == 'rdn':
                self.rdn()
            elif self.data[0] == 'resize':
                self.resize()
            elif self.data[0] == 'divide':
                self.divide()
            else:
                # 转换操作
                self.convert()

    def merge(self):
        self.N = len(self.data) // 2
        self.n = self.N

        tag = range(self.N)
        src = self.data[1::2]
        dst = self.data[2::2]
        args = list(zip(tag, src, dst))

        # 多线程加速
        with ThreadPoolExecutor() as pool:
            pool.map(self.merge_fitz, args)

    def merge_fitz(self, data):
        tag = int(data[0])
        src = pathlib.Path(data[1])
        dst = pathlib.Path(data[2])
        
        key = lambda i: [[pair[0], int(pair[1])] for pair in re.findall('([^0-9]*)([0-9]+)', i.stem)]
        paths = sorted(src.iterdir(), key=key)
        outputPath = str(dst.parent) + '/' + str(dst.stem)

        # 插入图像
        doc = fitz.open()
        imglist = []
        for f in paths:
            if f.is_file():
                if f.suffix in ['.jpg', '.png', '.jpeg', '.pdf']:
                    pdfbytes = fitz.open(str(f)).convert_to_pdf()
                    imgpdf = fitz.open('pdf', pdfbytes)
                    doc.insert_pdf(imgpdf)
                elif f.suffix == '.webp':
                    imglist.append(str(f))

        # 创建独立的合并文件
        if len(imglist) > 0:
            (maxw, maxh) = Image.open(str(imglist[0])).size
            c = canvas.Canvas(outputPath + '_webp.pdf', pagesize=portrait((maxw, maxh)))
            
            for i in range(len(imglist)):
                c.drawImage(imglist[i], 0, 0, maxw, maxh)
                c.showPage()
            c.save()

        # 不保存空的 pdf
        if len(doc) > 0:
            doc.save(outputPath + '.pdf')
        doc.close()

        # 发送数据
        self.n = self.n - 1
        self.pipe.send(str(tag + 1) + ',' + str(self.N) + ',' + str(dst) + ',' + str(self.n))

    def long(self):
        self.N = len(self.data) // 2
        self.n = self.N

        tag = range(self.N)
        src = self.data[1::2]
        dst = self.data[2::2]
        args = list(zip(tag, src, dst))

        # 多线程加速
        with ThreadPoolExecutor() as pool:
            pool.map(self.long_pil, args)

    def long_pil(self, data):
        tag = int(data[0])
        src = pathlib.Path(data[1])
        dst = pathlib.Path(data[2])
        
        key = lambda i: [[pair[0], int(pair[1])] for pair in re.findall('([^0-9]*)([0-9]+)', i.stem)]
        paths = sorted(src.iterdir(), key=key)
        outputPath = str(dst.parent) + '/' + str(dst.stem)

        # 获得所有图像
        paths = [f for f in paths if f.is_file() and f.suffix in ['.jpg', '.png', '.jpeg', '.webp']]

        # 创建独立的合并文件
        imglist = []
        if len(paths) > 0:
            img = Image.open(str(paths[0]))
            width = img.width
            
            # 注意宽高为整型，否则会出问题
            tHeight = 0
            for f in paths:
                img = Image.open(str(f))
                w, h = img.width, img.height
                height = int(h / w * width)
                tHeight = tHeight + height
                imglist.append(img)

            # 这里原本想修改图片大小，但是不知道为什么 Image.resize 函数调用会有问题 
            mergedImage = Image.new("RGB", (width, tHeight))

            tHeight = 0
            for img in imglist:
                mergedImage.paste(img, (0, tHeight))
                tHeight = tHeight + img.height

            mergedImage.save(outputPath + '.png')

        # 发送数据
        self.n = self.n - 1
        self.pipe.send(str(tag + 1) + ',' + str(self.N) + ',' + str(dst) + ',' + str(self.n))

    def compress(self):
        quality = int(self.data[1])
        self.N = (len(self.data) - 1) // 2
        self.n = self.N

        for i in range(self.N):
            src = pathlib.Path(self.data[i * 2 + 2])
            dst = pathlib.Path(self.data[i * 2 + 3])

            key = lambda i: [[pair[0], int(pair[1])] for pair in re.findall('([^0-9]*)([0-9]+)', i.stem)]
            paths = sorted(src.iterdir(), key=key)

            # 组合参数
            paths = [f for f in paths if f.is_file() and f.suffix in ['.jpg', '.png', '.jpeg', '.webp']]
            dsts = [dst] * len(paths)
            qualities = [quality] * len(paths)
            args = list(zip(paths, dsts, qualities))

            # 多线程加速
            with ThreadPoolExecutor() as pool:
                pool.map(self.compress_cv, args)

            # 发送数据
            self.n = self.n - 1
            self.pipe.send(str(i + 1) + ',' + str(self.N) + ',' + str(dst) + ',' + str(self.n))

    def compress_cv(self, data):
        # 获得源文件路径以及要保存的路径
        src = str(data[0])
        name = str(data[1]) + '/' + data[0].name

        # 计算图像大小
        srcSize = 0
        with open(src, 'rb') as f:
            srcSize = len(f.read()) // 1024
        dstSize = srcSize * data[2] / 100

        quality = 90
        step = 5
        img = cv2.imread(src)

        # 循环压缩直到达到目标大小
        while srcSize > dstSize:
            # 获得返回的第 2 个结果
            byte = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, quality])[1]
            if quality - step < 0:
                break

            quality -= step
            srcSize = len(byte) // 1024

        # 写入文件
        with open(name, 'wb') as f:
            f.write(BytesIO(byte).getvalue())

    def rdn(self):
        self.N = (len(self.data)) // 2
        self.n = self.N

        for i in range(self.N):
            src = pathlib.Path(self.data[i * 2 + 1])
            dst = pathlib.Path(self.data[i * 2 + 2])

            key = lambda i: [[pair[0], int(pair[1])] for pair in re.findall('([^0-9]*)([0-9]+)', i.stem)]
            paths = sorted(src.iterdir(), key=key)

            # 组合参数
            paths = [f for f in paths if f.is_file() and f.suffix in ['.jpg', '.png', '.jpeg', '.webp']]
            dsts = [dst] * len(paths)
            args = list(zip(paths, dsts))

            # 多线程加速
            with ThreadPoolExecutor() as pool:
                pool.map(self.rdn_noise_cancel, args)

            # 发送数据
            self.n = self.n - 1
            self.pipe.send(str(i + 1) + ',' + str(self.N) + ',' + str(dst) + ',' + str(self.n))

    def rdn_noise_cancel(self, data):
        # 获得源文件路径以及要保存的路径
        src = str(data[0])
        name = str(data[1]) + '/' + data[0].name

        # 使用 Pillow 读取并保存为 numpy 数组
        img = Image.open(src)
        lr_img = np.array(img)

        sr_img = self.model.predict(lr_img)
        dst = Image.fromarray(sr_img)
        dst.save(name)

    def resize(self):
        self.N = (len(self.data) - 2) // 2
        self.n = self.N

        for i in range(self.N):
            src = pathlib.Path(self.data[i * 2 + 3])
            dst = pathlib.Path(self.data[i * 2 + 4])

            key = lambda i: [[pair[0], int(pair[1])] for pair in re.findall('([^0-9]*)([0-9]+)', i.stem)]
            paths = sorted(src.iterdir(), key=key)

            # 组合参数
            paths = [f for f in paths if f.is_file() and f.suffix in ['.jpg', '.png', '.jpeg', '.webp']]
            dsts = [dst] * len(paths)
            args = list(zip(paths, dsts))

            # 多线程加速
            with ThreadPoolExecutor() as pool:
                pool.map(self.resize_cv, args)

            # 发送数据
            self.n = self.n - 1
            self.pipe.send(str(i + 1) + ',' + str(self.N) + ',' + str(dst) + ',' + str(self.n))

    def resize_cv(self, data):
        # 获得源文件路径以及要保存的路径
        src = str(data[0])
        name = str(data[1]) + '/' + data[0].name
        width = int(self.data[1])
        height = int(self.data[2])

        img = cv2.imread(src)

        # 当宽度为 0 时，就让高度一致
        if width == 0:
            h, w, d = img.shape
            width = int(height / h * w)

        # 当高度为 0 时，就让宽度一致
        if height == 0:
            h, w, d = img.shape
            height = int(width / w * h)

        res = cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)
        cv2.imwrite(name, res)

    def convert(self):
        self.N = (len(self.data)) // 2
        self.n = self.N

        for i in range(self.N):
            src = pathlib.Path(self.data[i * 2 + 1])
            dst = pathlib.Path(self.data[i * 2 + 2])

            key = lambda i: [[pair[0], int(pair[1])] for pair in re.findall('([^0-9]*)([0-9]+)', i.stem)]
            paths = sorted(src.iterdir(), key=key)

            # 组合参数
            paths = [f for f in paths if f.is_file() and f.suffix in ['.jpg', '.png', '.jpeg', '.webp']]
            dsts = [dst] * len(paths)
            args = list(zip(paths, dsts))

            # 多线程加速
            with ThreadPoolExecutor() as pool:
                pool.map(self.convert_pil, args)

            # 发送数据
            self.n = self.n - 1
            self.pipe.send(str(i + 1) + ',' + str(self.N) + ',' + str(dst) + ',' + str(self.n))

    def convert_pil(self, data):
        # 获得源文件路径以及要保存的路径
        src = str(data[0])
        suffix = pathlib.PurePath(data[0].name).suffix
        name = str(data[1]) + '/' + data[0].name[:-len(suffix)] + '.' + self.data[0]

        im = Image.open(src).convert('RGB')
        im.save(name, self.data[0])

    def divide(self):
        dir = self.data[1]
        src = self.data[2]

        #  打开 PDF 文件，生成一个对象
        doc = fitz.open(src)
        pages = [p for p in doc]
        dirs = [dir] * len(pages)
        tags = range(len(pages))
        args = list(zip(tags, dirs, pages))

        self.N = len(pages)
        self.n = self.N

        # 多线程加速
        with ThreadPoolExecutor() as pool:
            pool.map(self.divide_fitz, args)
            
    def divide_fitz(self, data):
        tag = int(data[0])
        dir = data[1]
        page = data[2]

        # 每个尺寸的缩放系数为 2，这将为我们生成分辨率提高 4 倍的图像。
        rotate = int(0)
        zoom_x, zoom_y = 2.0, 2.0
        trans = fitz.Matrix(zoom_x, zoom_y).prerotate(rotate)
        pm = page.get_pixmap(matrix=trans, alpha=False)
        pm.save(dir + '/' + '{:02}.png' .format(tag))

        # 发送数据
        self.n = self.n - 1
        self.pipe.send(str(tag + 1) + ',' + str(self.N) + ',' + str(dir) + ',' + str(self.n))


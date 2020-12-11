import requests
from lxml import etree
from time import time, sleep
import asyncio
import aiohttp
import json
import subprocess
import os
from threading import Thread


class BiliBili(object):

    def __init__(self):
        self.id = input("搜索名称:")
        self.urls = [
            "https://search.bilibili.com/all?keyword={m}&from_source=banner_search&page={k}".format(k=i, m=self.id) for
            i in range(1, 11)]
        self.headers = {
            "accept": "*/*",
            "accept-encoding": "identity",
            "accept-language": "zh-CN,zh-TW;q=0.9,zh;q=0.8,en-US;q=0.7,en;q=0.6,zh-HK;q=0.5",
            "origin": "https://www.bilibili.com",
            "range": "bytes=0-169123900000000",
            "referer": "https://www.bilibili.com/video/",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36"
        }

    # 发送请求访问
    async def getData(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return await response.text()

    # 获取一个页面的信息
    def parseData(self, data):
        # 创建element对象
        html = etree.HTML(data)
        # 获取全部视频节点
        data_html = html.xpath(
            '//*[@id="all-list"]/div[1]/div[2]/ul/li|//*[@id="all-list"]/div[1]/ul/li')
        # 从每个节点获取信息
        for li in data_html:
            # 标题
            name = li.xpath('./div/div[1]/a/@title')[0]
            # 详细链接
            link = "https:" + \
                str(li.xpath('./a/@href|./div[2]/div[1]/a[1]/@href')[0])
            # up主
            up = li.xpath('./div/div[3]/span[4]/a/text()')[0]
            # 上传时间
            up_time = li.xpath('./div/div[3]/span[3]/text()')[0].strip()
            yield {"name": name, "link": link, "up": up, "up_time": up_time}

    # 调度
    async def schedule(self, url, datalist):
        for html in self.parseData(await self.getData(url)):
            datalist.append(html)

    def run(self):
        datalist = []
        threads = []
        # 创建事件循环对象
        loop = asyncio.get_event_loop()
        start = time()
        for url in self.urls:
            threads.append(self.schedule(url, datalist))
        # 将协程对象注册到时间循环
        loop.run_until_complete(asyncio.wait(threads))
        loop.stop()
        for i, k in enumerate(datalist):
            print(
                '-----序号：{i}-----\nUP:{up}\n标题:{name}\n详细链接:{link}\n上传时间:{up_time}'.format(i=i, **k))
        end = time()
        print("搜索了{}秒".format(end - start))
        number = int(input("输入要下载视频的序号:"))
        vide = datalist[number]['link']
        return vide


class Download(BiliBili):
    def __init__(self):
        # 继承父类的属性
        BiliBili.__init__(self)
        # 保存的文件夹
        self.location = r'./Bilibili/'
        if not os.path.exists(self.location):
            os.mkdir(self.location)
        # 创建session对象
        self.session = requests.session()
        self.error_set = ['/', r'\\', ':', '*', '?', '"', '|', '<', '>']

    def download(self):
        video = self.run()
        requ = requests.get(video, headers=self.headers)
        data = requ.content.decode()
        # 定位到script
        html = etree.HTML(data)  # 创建element对象
        scripts = html.xpath("/html/head/script[5]/text()")[0]
        script = scripts.split("window.__playinfo__=")[1]
        # 将字符串转换成字典
        script_json = json.loads(script)
        # 获取标题
        title = html.xpath('//*[@id="viewbox_report"]/h1/@title')[0]
        for c in title:
            if c in self.error_set:
                title = title.replace(c, '')
        # 解析出视频和音频的地址
        video_url = script_json["data"]['dash']["video"][0]["baseUrl"]
        audio_url = script_json["data"]['dash']["audio"][0]["baseUrl"]
        return video_url, audio_url, title

    def video(self, video_url, title):
        # 请求视频
        videocontent = self.session.get(
            video_url, headers=self.headers).content
        # 保存视频
        with open(self.location + '%s.m4s' % title, 'wb') as f:
            f.write(videocontent)
            f.close()

    def audio(self, audio_url, title):
        # 请求音频
        audiocontent = self.session.get(
            audio_url, headers=self.headers).content
        # 保存音频
        with open(self.location + '%s.mp3' % title, 'wb') as f:
            f.write(audiocontent)
            f.close()

    def ffmpeg(self, title):
        # 将视音频合并到一个文件
        command = f'ffmpeg -i "{self.location + title}.m4s" -i "{self.location + title}.mp3" -c copy "{self.location + title}.mp4" -loglevel quiet'
        subprocess.Popen(command, shell=True)

    def delete(self, title):
        # 删除多余的文件
        sleep(5)
        os.remove(self.location + f"{title}.m4s")
        os.remove(self.location + f"{title}.mp3")

    def main(self):
        video_url, audio_url, title = self.download()
        print(f'开始下载:{title} ')
        start = time()
        # 开启多线程，保存音视频
        videothread = Thread(target=self.video, args=(video_url, title))
        audiothread = Thread(target=self.audio, args=(audio_url, title))
        videothread.start()
        audiothread.start()
        videothread.join()
        audiothread.join()
        # 退出保持会话
        self.session.close()
        # 将音视频合并到一个文件
        self.ffmpeg(title)
        # 删除多余的文件
        self.delete(title)
        print(f'下载完成:{title}')
        end = time()
        print("下载所花了{}秒".format(end - start))


if __name__ == '__main__':
    while True:
        download = Download()
        download.main()
        n=input("选择\n1：退出\n其余继续")
        if n=="1":
            break

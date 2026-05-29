import asyncio

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp 
from jmcomic import JmAlbumDetail, JmOption, JmcomicException, JsonResolveFailException, MissingAlbumPhotoException, RequestRetryAllFailException
import os 

@register("astrbot_plugin_jm", "yuki", "提供查看、下载JM漫画的指令", "v1.1")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

        # 客户端只创建一次，复用
        self.client = JmOption.default().new_jm_client()
        # 提前算好封面目录路径
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.album_cover_dir = os.path.join(script_dir, 'album_cover')
        # 确保目录存在
        os.makedirs(self.album_cover_dir, exist_ok=True)

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""

    @filter.command("jm")
    async def get_album(self, event: AstrMessageEvent, id: str):
        """返回PDF格式的本子""" 

    @filter.command("jmv") 
    async def bower_album(self, event: AstrMessageEvent, id: str): 
        """仅返回对应本子的信息"""
    
    @filter.command("获取封面")
    async def get_cover(self, event: AstrMessageEvent, album_id: str):
        """返回对应本子的封面"""
        # 输入校验，防止路径穿越和无效输入
        if not album_id.isdigit():
            yield event.plain_result("id 格式不正确，应为纯数字")
            return

        cover_path = os.path.join(self.album_cover_dir, f'{album_id}.png')

        # 不存在则下载
        if not os.path.exists(cover_path):
            try:
                # 同步函数放到线程池，避免阻塞事件循环
                await asyncio.to_thread(
                    self.client.download_album_cover,
                    album_id,
                    f'{self.album_cover_dir}.png'
                )
            except Exception as e:
                yield event.plain_result(f"封面下载失败：{e}")
                return

            # 下载完再次确认文件确实生成了
            if not os.path.exists(cover_path):
                yield event.plain_result("下载完成但未找到封面文件，可能是 id 无效")
                return

        # 返回封面图
        yield event.chain_result([
            Comp.At(qq=event.get_sender_id()),
            Comp.Image.fromFileSystem(cover_path)
        ])

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""


JmOption.default().to_file('./option.yml') 

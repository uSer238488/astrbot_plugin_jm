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

    @filter.command("获取详情") 
    async def bower_album(self, event: AstrMessageEvent, album_id: str): 
        """返回对应本子的详情"""

        from astrbot.api.message_components import Node, Plain

        # 输入校验，防止路径穿越和无效输入
        if not album_id.isdigit(): 
            yield event.plain_result("id 格式不正确，车牌号应为纯数字") 
            return 
        
        # 获取本子
        try: 
            # album_detail: JmAlbumDetail = self.client.get_album_detail(album_id)
            album_detail: JmAlbumDetail = await asyncio.to_thread(self.client.get_album_detail, album_id)
        except MissingAlbumPhotoException:
            yield event.plain_result("本子不存在或已被删除")
            return
        except JmcomicException as e:
            yield event.plain_result(f"获取失败：{e}")
            return
        except Exception as e:
            logger.exception("get_album_detail 异常")  # 留日志
            yield event.plain_result("获取本子失败，请稍后再试")
            return

        # 生成结果
        res = []
        res.append(f"📖 标题:  {album_detail.name}")
        res.append(f"🆔 ID:  JM{album_id}")
        res.append(f"🔗 链接:  https://18comic.vip/album/{album_id}/")
        
        if album_detail.description: 
            res.append(f"🤔描述: {album_detail.description}")

        authors = ",".join(album_detail.authors) 
        res.append(f"✍️ 作者:   {authors}")
        res.append(f"📅 发布日期:   {album_detail.pub_date}")
        res.append(f"📅 更新日期:  {album_detail.update_date}")
        res.append(f"📄 总页数:  {album_detail.page_count}")
        res.append(f"👀 观看:   {album_detail.views}")
        res.append(f"❤️ 点赞:  {album_detail.likes}")
        res.append(f"💬 评论:   {album_detail.comment_count}")

        tags = ",".join(album_detail.tags)
        res.append(f"🏷️ 标签:  {tags}")

        actors = ",".join(album_detail.actors)
        res.append(f"🎭 人物:  {actors}")

        works = ",".join(album_detail.works)
        res.append(f"📚 作品:  {works}")

        episode_list = "\n".join(f"{episode[0]} {episode[1]} {episode[2]}" for episode in album_detail.episode_list)
        res.append(f"📑 章节 ({len(album_detail.episode_list)}):  \n{episode_list}")

        # yield event.plain_result("\n".join(res))
        node = Node(
            uin = 2630903225,
            name = "白丝协会会长",
            content = [
                Plain("\n".join(res))
            ]
        )
        yield event.chain_result([node]) 

    
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
                    cover_path
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

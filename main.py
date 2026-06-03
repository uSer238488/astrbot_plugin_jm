from pathlib import Path
import asyncio
import os 


from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
from astrbot.core.utils.astrbot_path import get_astrbot_data_path
import astrbot.api.message_components as Comp 


from jmcomic import JmAlbumDetail, JmOption, JmcomicException, JsonResolveFailException, MissingAlbumPhotoException, RequestRetryAllFailException, create_option_by_file, download_album, Feature, download_photo


@register("astrbot_plugin_jm", "yuki", "提供查看、下载JM漫画的指令", "v1.1")
class MyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)

        # 获取黑名单群聊
        self.blacklist: list[str] = [str(gid) for gid in config.get("group_blacklist", [])] if config else []

        # 存储文件路径
        # script_dir = os.path.dirname(os.path.abspath(__file__))
        plugin_data_path = Path(get_astrbot_data_path()) / "plugin_data" / self.name 

        # 本子封面文件夹路径
        self.album_cover_dir = os.path.join(plugin_data_path, "album_cover")

        # 本子本体文件夹路径
        self.album_dir = os.path.join(plugin_data_path, "album") 

        # 章节本体文件夹
        self.photo_dir = os.path.join(plugin_data_path, "photo") 

        # 把本子和章节本体文件夹路径写入环境变量
        os.environ["JM_DOWNLOAD_DIR"] = os.path.join(plugin_data_path) 

        # 通过配置文件来创建option对象
        self.option = create_option_by_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), "option.yml"))

        # 确保目录存在
        os.makedirs(self.album_cover_dir, exist_ok = True)
        os.makedirs(self.album_dir, exist_ok = True)
        os.makedirs(self.photo_dir, exist_ok = True)

        # 创建客户端
        self.client = self.option.new_jm_client()

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""

    @filter.command("jm")
    async def get_album(self, event: AstrMessageEvent, album_id: str):
        """返回PDF格式的本子""" 

        # 黑名单群聊，有内鬼，终止交易
        if await self.check_group_id(event): 
            yield event.chain_result([
                Comp.At(qq = event.get_sender_id()),
                Comp.Plain("有内鬼，终止交易！")
            ])
            return 
        
        # 输入校验，防止路径穿越和无效输入
        if not album_id.isdigit(): 
            yield event.plain_result("❌id格式不正确!") 
            return 
        
        # 获取本子详情
        try: 
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
        
        # 如果本子有多个章节则直接中断，并且引导用户使用jmp指令
        if len(album_detail.episode_list) > 1: 
            yield event.chain_result([
                Comp.At(qq = event.get_sender_id()),
                Comp.Plain("本子有多个章节，请使用 /获取详情 id 指令获取所有章节的id，然后使用 /jmp id 指令单独下载某个章节") 
            ])
            return 
        
        # 合成文件路径
        res_path = os.path.join(self.album_dir, f"{album_id}.pdf") 

        # 下载本子到指定目录、文件名为: {album_id}.pdf
        if not os.path.exists(res_path): 
            yield event.plain_result(f"开始下载: \njm{album_id}, \n请稍候...")
            try: 
                await asyncio.to_thread(
                    download_album, 
                    album_id, 
                    self.option,
                    extra = Feature.export_pdf(
                        pdf_dir = self.album_dir,
                        filename_rule = "Aid",
                        delete_original_file=True,
                    )
                )
            except Exception as e: 
                logger.exception(f"download_album failed, {type(e).__name__}: {e}") 
                yield event.plain_result("下载失败，可能是本子不存在或者需要登录才能下载") 
                return 

        # 没有找到文件
        if not os.path.exists(res_path): 
            yield event.plain_result("下载完成但是没有找到文件") 
            return 
        
        # 返回结果
        yield event.chain_result([
            Comp.At(qq=event.get_sender_id()),
            Comp.Plain(f" JM{album_id} 下载完成。\n大文件发送可能较慢, 请耐心等待"),
        ])
        yield event.chain_result([
            Comp.File(file=res_path, name=f"JM{album_id}.pdf"),
        ])


    @filter.command("jmp") 
    async def get_photo(self, event: AstrMessageEvent, photo_id: str): 
        """返回PDF格式的章节"""

        # 黑名单群聊，有内鬼，终止交易
        if await self.check_group_id(event): 
            yield event.chain_result([
                Comp.At(qq = event.get_sender_id()),
                Comp.Plain("有内鬼，终止交易！")
            ])
            return 
        
        # 输入校验，防止路径穿越和无效输入
        if not photo_id.isdigit(): 
            yield event.plain_result("❌id格式不正确!") 
            return 
        
        # 合成文件路径
        res_path = os.path.join(self.album_dir, f"{photo_id}.pdf") 

        # 下载本子到指定目录、文件名为: {photo_id}.pdf
        if not os.path.exists(res_path): 
            yield event.plain_result(f"开始下载: \njm{photo_id}, \n请稍候...")
            try: 
                await asyncio.to_thread(
                    download_photo, 
                    photo_id, 
                    self.option,
                    extra = Feature.export_pdf(
                        pdf_dir = self.photo_dir,
                        filename_rule = "Pid",
                        delete_original_file=True,
                    )
                )
            except Exception as e: 
                logger.exception(f"download_photo failed, {type(e).__name__}: {e}") 
                yield event.plain_result("下载失败，可能是章节不存在或者需要登录才能下载") 
                return 

        # 没有找到文件
        if not os.path.exists(res_path): 
            yield event.plain_result("下载完成但是没有找到文件") 
            return 
        
        # 返回结果
        yield event.chain_result([
            Comp.At(qq=event.get_sender_id()),
            Comp.Plain(f" JM{photo_id} 下载完成。\n大文件发送可能较慢, 请耐心等待"),
        ])
        yield event.chain_result([
            Comp.File(file=res_path, name=f"JM{photo_id}.pdf"),
        ])


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
        # res.append(f"📅 发布日期:   {album_detail.pub_date}")
        # res.append(f"📅 更新日期:  {album_detail.update_date}")
        # res.append(f"📄 总页数:  {album_detail.page_count}")
        res.append(f"👀 观看:   {album_detail.views}")
        res.append(f"❤️ 点赞:  {album_detail.likes}")
        res.append(f"💬 评论:   {album_detail.comment_count}")

        tags = ",".join(album_detail.tags)
        res.append(f"🏷️ 标签:  {tags}")

        actors = ",".join(album_detail.actors)
        res.append(f"🎭 人物:  {actors}")

        works = ",".join(album_detail.works)
        res.append(f"📚 作品:  {works}")

        episode_list = "\n".join(f"{episode[1]}  {episode[2]} (ID: {episode[0]})" for episode in album_detail.episode_list)
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

        # 黑名单群聊，终止交易
        if await self.check_group_id(event): 
            yield event.chain_result([
                Comp.At(qq = event.get_sender_id()),
                Comp.Plain("有内鬼，终止交易！")
            ])
            return 
        
        # 输入校验，防止路径穿越和无效输入
        if not album_id.isdigit():
            yield event.plain_result("id 格式不正确，应为纯数字")
            return

        cover_path = os.path.join(self.album_cover_dir, f'{album_id}.jpg')

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

    async def check_group_id(self, event: AstrMessageEvent): 
        """检查群号是否在黑名单内"""

        # 获取群聊id
        group_id = event.get_group_id()

        # 返回结果
        return (group_id in self.blacklist)


    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""


# JmOption.default().to_file('./option.yml') 
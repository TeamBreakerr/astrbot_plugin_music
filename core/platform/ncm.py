from typing import ClassVar

from astrbot.api import logger

from ..config import PluginConfig
from ..model import Platform, Song
from .base import BaseMusicPlayer


class NetEaseMusic(BaseMusicPlayer):
    """
    网易云音乐（Web API）
    """

    platform: ClassVar[Platform] = Platform(
        name="netease",
        display_name="网易云音乐",
        keywords=["网易云", "网易点歌"],
    )

    def __init__(self, config: PluginConfig):
        super().__init__(config)

    async def fetch_songs(self, keyword: str, limit=5, extra=None) -> list[Song]:
        result = await self._request(
            url="http://music.163.com/api/search/get/web",
            method="POST",
            data={"s": keyword, "limit": limit, "type": 1, "offset": 0},
            cookies={"appver": "2.0.2"},
        )
        if (
            not isinstance(result, dict)
            or "result" not in result
            or "songs" not in result["result"]
        ):
            logger.error(f"返回了意料之外数据：{result}")
            return []

        songs = result["result"]["songs"][:limit]

        return [
            Song(
                id=s.get("id"),
                name=s.get("name"),
                artists="、".join(a["name"] for a in s["artists"]),
                duration=s.get("duration"),
            )
            for s in songs
        ]

    async def fetch_extra(self, song: Song) -> Song:
        """
        fork 改版：
        - 音频直链：走自建网易云增强API(解锁VIP、稳定320k)
        - 封面：走网易官方API(原项目接口家族)，拉成高清大图
        其余(歌词/评论)仍沿用原项目实现。
        """
        # 1) 音频直链：自建增强API
        if not song.audio_url:
            try:
                base = self.cfg.audio_api_base_url.rstrip("/")
                result = await self._request(
                    f"{base}/song/url/v1?id={song.id}&level=exhigh"
                )
                data = result.get("data") if isinstance(result, dict) else None
                if data and data[0].get("url"):
                    song.audio_url = data[0]["url"]
                else:
                    logger.warning(f"增强API未返回音频直链：{song.name}")
            except Exception as e:
                logger.warning(f"增强API取音频失败({song.name}): {e}")

        # 2) 封面：网易官方API，拉高清
        if not song.cover_url:
            try:
                result = await self._request(
                    f"https://music.163.com/api/song/detail/?ids=[{song.id}]"
                )
                detail = result.get("songs") if isinstance(result, dict) else None
                if detail:
                    album = detail[0].get("album") or detail[0].get("al") or {}
                    pic = album.get("picUrl")
                    if pic:
                        song.cover_url = f"{pic}?param={self.cfg.cover_param}"
            except Exception as e:
                logger.warning(f"网易官方API取封面失败({song.name}): {e}")

        return song

# -*- coding: utf-8 -*-
# (c) YashDK [yash-dk@github]
# (c) modified by AmirulAndalib [amirulandalib@github]
import logging
from datetime import datetime

from telethon.errors.rpcerrorlist import FloodWaitError, MessageNotModifiedError
from telethon.tl.types import KeyboardButtonCallback

from ...functions.Human_Format import human_readable_bytes, human_readable_timedelta
from ..getVars import get_val

torlog = logging.getLogger(__name__)


class Status:
    # Shared List
    Tasks = []

    def __init__(self):
        self._task_id = len(self.Tasks) + 1

    def refresh_info(self):
        raise NotImplementedError

    def update_message(self):
        raise NotImplementedError

    def is_active(self):
        raise NotImplementedError

    def set_inactive(self):
        raise NotImplementedError


# qBittorrent Task Class
class QBTask(Status):
    def __init__(self, torrent, message, client):
        super().__init__()
        self.Tasks.append(self)
        self.hash = torrent.hash
        self._torrent = torrent
        self._message = message
        self._client = client
        self._active = True
        self._path = torrent.save_path
        self._error = ""
        self._done = False
        self.cancel = False
        self._omess = None
        self._prevmsg = ""

    async def set_original_mess(self, omess):
        self._omess = omess

    async def get_original_message(self):
        return self._omess

    async def refresh_info(self, torrent=None):
        if torrent is None:
            self._torrent = self._client.torrents_info(
                torrent_hashes=self._torrent.hash
            )
        else:
            self._torrent = torrent

    async def get_sender_id(self):
        return self._omess.sender_id

    async def create_message(self):
        msg = (
            f"<b>Downloading:</b> <code>{self._torrent.name}</code>\n"
            + f'<b>Down:</b> {human_readable_bytes(self._torrent.dlspeed, postfix="/s")} <b>Up:</b> {human_readable_bytes(self._torrent.upspeed, postfix="/s")}\n'
        )

        msg += f"<b>Progress:</b> {self.progress_bar(self._torrent.progress)} - {round(self._torrent.progress * 100, 2)}%\n"

        msg += f"<b>Downloaded:</b> {human_readable_bytes(self._torrent.downloaded)} of {human_readable_bytes(self._torrent.total_size)}\n"

        msg += f"<b>ETA:</b> <b>{human_readable_timedelta(self._torrent.eta)}</b>\n"
        msg += f"<b>S:</b>{self._torrent.num_seeds} <b>L:</b>{self._torrent.num_leechs}\n"

        msg += "<b>Using engine:</b> <code>qBittorrent</code>"

        return msg

    async def get_state(self):
        # stalled
        if self._torrent.state == "stalledDL":
            return f"Torrent <code>{self._torrent.name}</code> is stalled(waiting for connection) temporarily."

        elif self._torrent.state == "metaDL":
            return f'Getting metadata for {self._torrent.name} - {datetime.now().strftime("%H:%M:%S")}'

        elif (
            self._torrent.state == "downloading"
            or self._torrent.state.lower().endswith("dl")
        ):
            # kept for past ref
            return None

    async def central_message(self):
        cstate = await self.get_state()
        return cstate if cstate is not None else await self.create_message()

    async def update_message(self):
        msg = await self.create_message()
        if self._prevmsg == msg:
            return

        self._prevmsg = msg

        try:

            cstate = await self.get_state()

            msg = cstate if cstate is not None else msg

            await self._message.edit(
                msg, parse_mode="html", buttons=self._message.reply_markup
            )

        except MessageNotModifiedError as e:
            torlog.debug(f"{e}")
        except FloodWaitError as e:
            torlog.error(f"{e}")
        except Exception as e:
            torlog.info(f"Not expected {e}")

    async def set_done(self):
        self._done = True
        await self.set_inactive()

    def is_done(self):
        return self._done

    async def set_path(self, path):
        self._path = path

    async def get_path(self):
        return self._path

    async def set_inactive(self, error=None):
        self._active = False
        if error is not None:
            self._error = error

    async def is_active(self):
        return self._active

    def progress_bar(self, percentage):
        """Returns a progress bar for download"""
        # percentage is on the scale of 0-1
        comp = get_val("COMPLETED_STR")
        ncomp = get_val("REMAINING_STR")
        return "".join(
            comp if i <= int(percentage * 10) else ncomp for i in range(1, 11)
        )


class ARTask(Status):
    def __init__(self, gid, message, aria2, dl_file):
        super().__init__()
        self.Tasks.append(self)
        self._gid = gid
        self._dl_file = dl_file
        self._message = message
        self._aria2 = aria2
        self._active = True
        self._error = ""
        self._done = False
        self.cancel = False
        self._omess = None
        self._path = None
        self._prevmsg = ""

    # Setters

    async def set_original_mess(self, omess=None):
        if omess is None:
            omess = await self._message.get_reply_message()

        self._omess = omess

    async def get_original_message(self):
        return self._omess

    async def get_gid(self):
        return self._gid

    async def set_gid(self, gid):
        self._gid = gid

    async def get_sender_id(self):
        return self._omess.sender_id

    async def refresh_info(self, dl_file=None):
        if dl_file is None:
            try:
                self._dl_file = self._aria2.get_download(self._gid)
            except:
                torlog.exception("Errored in fetching the direct DL.")
        else:
            self._dl_file = dl_file

    async def create_message(self):
        # Getting the vars pre handed
        downloading_dir_name = "N/A"
        try:
            downloading_dir_name = str(self._dl_file.name)
        except:
            pass

        msg = (
            f"<b>Downloading:</b> <code>{downloading_dir_name}</code>\n"
            + f"<b>Down:</b> {self._dl_file.download_speed_string()} <b>Up:</b> {self._dl_file.upload_speed_string()}\n"
        )

        msg += f"<b>Progress:</b> {self.progress_bar(self._dl_file.progress / 100)} - {round(self._dl_file.progress, 2)}%\n"

        msg += f"<b>Downloaded:</b> {human_readable_bytes(self._dl_file.completed_length)} of {human_readable_bytes(self._dl_file.total_length)}\n"

        msg += f"<b>ETA:</b> <b>{self._dl_file.eta_string()}</b>\n"
        msg += f"<b>Conns:</b>{self._dl_file.connections} <b>\n"
        msg += "<b>Using engine:</b> <code>Aria2 For DirectLinks</code>"

        return msg

    async def get_state(self):
        # No states for aria2
        pass

    async def central_message(self):
        return await self.create_message()

    async def update_message(self):
        msg = await self.create_message()
        if self._prevmsg == msg:
            return

        self._prevmsg = msg

        try:
            data = f"torcancel aria2 {self._gid} {self._omess.sender_id}"
            await self._message.edit(
                msg,
                parse_mode="html",
                buttons=[
                    KeyboardButtonCallback(
                        "Cancel Direct Leech", data=data.encode("UTF-8")
                    )
                ],
            )

        except MessageNotModifiedError as e:
            torlog.debug(f"{e}")
        except FloodWaitError as e:
            torlog.error(f"{e}")
        except Exception as e:
            torlog.info(f"Not expected {e}")

    async def set_done(self):
        self._done = True
        await self.set_inactive()

    def is_done(self):
        return self._done

    async def set_inactive(self, error=None):
        self._active = False
        if error is not None:
            self._error = error

    async def is_active(self):
        return self._active

    async def get_error(self):
        return self._error

    async def set_path(self, path):
        self._path = path

    async def get_path(self):
        return self._path

    def progress_bar(self, percentage):
        """Returns a progress bar for download"""
        # percentage is on the scale of 0-1
        comp = get_val("COMPLETED_STR")
        ncomp = get_val("REMAINING_STR")
        return "".join(
            comp if i <= int(percentage * 10) else ncomp for i in range(1, 11)
        )


class MegaDl(Status):
    def __init__(self, add_info, dl_info, message, mega_client):
        super().__init__()
        self.Tasks.append(self)
        self._gid = add_info["gid"]
        self._dl_info = dl_info
        self._message = message
        self._mega_client = mega_client
        self._active = True
        self._error = ""
        self._done = False
        self.cancel = False
        self._omess = None
        self._path = add_info["dir"]
        self._prevmsg = ""

    # Setters

    async def set_original_mess(self, omess=None):
        if omess is None:
            omess = await self._message.get_reply_message()

        self._omess = omess

    async def get_original_message(self):
        return self._omess

    async def get_gid(self):
        return self._gid

    async def set_gid(self, gid):
        self._gid = gid

    async def get_sender_id(self):
        return self._omess.sender_id

    async def refresh_info(self, dl_info=None):
        if dl_info is None:
            try:
                self._dl_info = self._aria2.get_download(self._gid)
            except:
                torlog.exception("Errored in fetching the direct DL.")
        else:
            self._dl_info = dl_info

    async def create_message(self):
        msg = (
            f'<b>Downloading:</b> <code>{self._dl_info["name"]}</code>\n'
            + f'<b>Speed:</b> {human_readable_bytes(self._dl_info["speed"])}\n'
        )

        msg += "<b>Progress:</b> {} - {}%\n".format(
            self.progress_bar(
                (self._dl_info["completed_length"] / self._dl_info["total_length"])
            ),
            round(
                (self._dl_info["completed_length"] / self._dl_info["total_length"])
                * 100,
                2,
            ),
        )
        msg += f'<b>Downloaded:</b> {human_readable_bytes(self._dl_info["completed_length"])} of {human_readable_bytes(self._dl_info["total_length"])}\n'

        msg += "<b>ETA:</b> <b>N/A</b>\n"

        msg += "<b>Using engine:</b> <code>Mega DL</code>"

        return msg

    async def get_state(self):
        # No states for aria2
        pass

    async def central_message(self):
        return await self.create_message()

    async def update_message(self):
        msg = await self.create_message()
        if self._prevmsg == msg:
            return

        self._prevmsg = msg

        try:
            data = f"torcancel megadl {self._gid} {self._omess.sender_id}"
            await self._message.edit(
                msg,
                parse_mode="html",
                buttons=[
                    KeyboardButtonCallback("Cancel Mega DL", data=data.encode("UTF-8"))
                ],
            )

        except MessageNotModifiedError as e:
            torlog.debug(f"{e}")
        except FloodWaitError as e:
            torlog.error(f"{e}")
        except Exception as e:
            torlog.info(f"Not expected {e}")

    async def set_done(self):
        self._done = True
        await self.set_inactive()

    def is_done(self):
        return self._done

    async def set_inactive(self, error=None):
        self._active = False
        if error is not None:
            self._error = error

    async def is_active(self):
        return self._active

    async def get_error(self):
        return self._error

    async def set_path(self, path):
        self._path = path

    async def get_path(self):
        return self._path

    def progress_bar(self, percentage):
        """Returns a progress bar for download"""
        # percentage is on the scale of 0-1
        comp = get_val("COMPLETED_STR")
        ncomp = get_val("REMAINING_STR")
        return "".join(
            comp if i <= int(percentage * 10) else ncomp for i in range(1, 11)
        )

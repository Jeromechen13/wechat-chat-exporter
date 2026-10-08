# WeChat Chat Exporter

A small Windows utility for exporting selected WeChat contacts or group chats from the local WeChat database.

It uses [`wechatauto-replica`](https://pypi.org/project/wechatauto-replica/) to read local WeChat databases, resolves a contact/group by nickname or remark, exports the complete available message history, optionally filters message types, and writes JSON and/or UTF-8 TXT files.

> This repository contains **code only**. Do not commit real chat exports, WeChat databases, database keys, wxids, phone numbers, or other personal data.

## Features

- Export one or more specified contacts / group chats
- Read all locally available history (`limit_per_chat=None`)
- Export JSON and UTF-8 TXT
- Filter message types such as video
- Accept nickname, remark, `wxid_...`, or `...@chatroom`
- Temporary unfiltered export is deleted automatically
- No chat data is uploaded by this script

## Requirements

- Windows 10 / 11
- Python 3.12 recommended
- Desktop WeChat installed and logged in
- `wechatauto-replica==1.2.5.1`

## Setup

Open PowerShell:

```powershell
git clone <your-repository-url>
cd wechat-chat-exporter

py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Check whether the local WeChat databases can be decrypted:

```powershell
python -m wechatauto doctor
```

For text/history export, the important line is similar to:

```text
数据库密钥：23/23 个库可解密
```

An image AES-key warning does not prevent text/history export. It matters mainly when decrypting image files.

## Configuration

Copy the example config:

```powershell
Copy-Item .\config.example.json .\config.json
```

Edit `config.json`:

```json
{
  "targets": [
    "Alice",
    "Project Group"
  ],
  "output_dir": "D:\\WeChatExport",
  "exclude_types": ["视频"],
  "write_json": true,
  "write_txt": true
}
```

`targets` can contain:

- contact nickname
- contact remark
- group-chat name
- `wxid_xxx`
- `xxxxxxxx@chatroom`

`config.json` is ignored by Git because real chat names and local paths may be private.

## Run

```powershell
python .\export_chats.py
```

Or specify a different config:

```powershell
python .\export_chats.py --config .\my-config.json
```

Example output:

```text
已确认：Alice -> wxid_xxxxx
已确认：Project Group -> 123456789@chatroom

原始读取完成：2 个会话，7417 条消息

Alice：原始 5429 | 排除 25 | 保留 5404
Project Group：原始 1988 | 排除 38 | 保留 1950

全部完成。输出目录：D:\WeChatExport
```

## Output

For each chat, the script can create:

```text
<chat>_全部历史_排除-视频.json
<chat>_全部历史_排除-视频.txt
```

JSON keeps structured fields such as timestamps, sender information, message type, content, IDs, and sequence information. TXT is easier to read manually.

## Privacy and safety

This project is intended only for exporting data from your own WeChat account and local computer.

The `.gitignore` intentionally excludes:

- `config.json`
- JSON / TXT / SQLite exports
- WeChat databases
- key directories
- environment/secrets files

Before every `git add` / `git push`, it is still a good idea to run:

```powershell
git status
```

and verify that no private data is staged.

## Notes

- "All history" means all history currently present and readable in the local WeChat databases. Deleted or never-synced messages cannot be recovered by this tool.
- Filtering a video message removes its message record from the final JSON/TXT. The temporary unfiltered JSON is deleted after successful processing.
- Media-file extraction (images, voice, video, attachments) is a separate task from exporting message metadata/content.

## License

This repository does not redistribute `wechatauto-replica`; it only depends on the package through PyPI. Review the dependency project's own license before redistribution or commercial use.

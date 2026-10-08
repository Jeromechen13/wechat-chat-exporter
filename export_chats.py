from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from wechatauto import WeChatDB


VIDEO_TYPE_CODES = {43}


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    targets = cfg.get("targets")
    if not isinstance(targets, list) or not targets:
        raise ValueError("config.json 中的 targets 必须是非空数组")

    output_dir = cfg.get("output_dir")
    if not output_dir:
        raise ValueError("config.json 中必须设置 output_dir")

    cfg.setdefault("exclude_types", ["视频"])
    cfg.setdefault("write_json", True)
    cfg.setdefault("write_txt", True)
    return cfg


def resolve_chat(db: WeChatDB, name: str) -> str:
    """Resolve a nickname/remark/group name to a unique WeChat username."""
    username = db.username_by_nickname(name)
    if username:
        return username

    hits = db.search_contact(name)
    exact = [
        h for h in hits
        if h.get("nick_name") == name or h.get("remark") == name
    ]

    if len(exact) == 1:
        return exact[0]["username"]
    if len(hits) == 1:
        return hits[0]["username"]

    if not hits:
        raise RuntimeError(f"找不到会话：{name}")

    preview = "\n".join(
        f"  - username={h.get('username')} | nick={h.get('nick_name')} | remark={h.get('remark')}"
        for h in hits[:20]
    )
    raise RuntimeError(
        f"「{name}」匹配到多个联系人/群聊，无法唯一确定：\n{preview}\n"
        "请在 config.json 中把该 target 改成更精确的备注名/昵称，"
        "或直接使用对应 username。"
    )


def format_time(ts: Any) -> str:
    try:
        return dt.datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)


def should_exclude(message: dict[str, Any], exclude_types: set[str]) -> bool:
    msg_type = str(message.get("type") or "")
    type_code = message.get("type_code")

    if msg_type in exclude_types:
        return True

    # WeChat local_type/type_code 43 = video.
    if "视频" in exclude_types and type_code in VIDEO_TYPE_CODES:
        return True

    return False


def export_chat(
    display_name: str,
    username: str,
    messages: list[dict[str, Any]],
    output_dir: Path,
    exclude_types: set[str],
    write_json: bool,
    write_txt: bool,
    exported_at: str | None,
) -> tuple[int, int, int]:
    original_count = len(messages)
    kept = [m for m in messages if not should_exclude(m, exclude_types)]
    excluded_count = original_count - len(kept)

    safe_name = "".join(
        "_" if c in '<>:"/\\|?*' else c
        for c in display_name
    ).strip() or "chat"

    suffix = ""
    if exclude_types:
        suffix = "_排除-" + "-".join(sorted(exclude_types))

    if write_json:
        json_path = output_dir / f"{safe_name}_全部历史{suffix}.json"
        payload = {
            "chat_name": display_name,
            "username": username,
            "exported_at": exported_at,
            "message_count": len(kept),
            "excluded_count": excluded_count,
            "excluded_types": sorted(exclude_types),
            "messages": kept,
        }
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    if write_txt:
        txt_path = output_dir / f"{safe_name}_全部历史{suffix}.txt"
        with txt_path.open("w", encoding="utf-8") as f:
            f.write(f"会话：{display_name}\n")
            f.write(f"username：{username}\n")
            f.write(f"原始消息：{original_count} 条\n")
            f.write(f"排除消息：{excluded_count} 条\n")
            f.write(f"最终保留：{len(kept)} 条\n")
            f.write(f"排除类型：{', '.join(sorted(exclude_types)) or '无'}\n")
            f.write("=" * 80 + "\n\n")

            for m in kept:
                time_str = format_time(m.get("create_time"))
                sender = m.get("sender_name") or m.get("sender_id") or "未知"
                msg_type = m.get("type") or ""
                content = m.get("content") or ""
                f.write(f"[{time_str}] {sender} [{msg_type}]\n{content}\n\n")

    return original_count, excluded_count, len(kept)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export selected WeChat chats to JSON/TXT using wechatauto-replica."
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="配置文件路径，默认 config.json",
    )
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    output_dir = Path(os.path.expandvars(os.path.expanduser(cfg["output_dir"])))
    output_dir.mkdir(parents=True, exist_ok=True)

    targets = [str(x).strip() for x in cfg["targets"] if str(x).strip()]
    exclude_types = {str(x).strip() for x in cfg.get("exclude_types", []) if str(x).strip()}

    db = WeChatDB()

    resolved: dict[str, str] = {}
    for target in targets:
        # Direct usernames are accepted too.
        if target.endswith("@chatroom") or target.startswith("wxid_"):
            username = target
        else:
            username = resolve_chat(db, target)

        resolved[target] = username
        print(f"已确认：{target} -> {username}")

    # export_history() is the safest way to fetch the complete chat history.
    # Use a temporary JSON so excluded message types never remain in the final output.
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            prefix="wechat_export_",
            dir=output_dir,
            delete=False,
            encoding="utf-8",
        ) as tmp:
            temp_path = Path(tmp.name)

        result = db.export_history(
            str(temp_path),
            fmt="json",
            users=list(resolved.values()),
            limit_per_chat=None,
        )
        print(f"\n原始读取完成：{result['chats']} 个会话，{result['messages']} 条消息")

        with temp_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        all_messages = data.get("messages", [])
        exported_at = data.get("exported_at")

        print()
        for display_name, username in resolved.items():
            chat_messages = [
                m for m in all_messages
                if m.get("chat") == username
            ]
            original, excluded, kept = export_chat(
                display_name=display_name,
                username=username,
                messages=chat_messages,
                output_dir=output_dir,
                exclude_types=exclude_types,
                write_json=bool(cfg.get("write_json", True)),
                write_txt=bool(cfg.get("write_txt", True)),
                exported_at=exported_at,
            )
            print(
                f"{display_name}：原始 {original} | "
                f"排除 {excluded} | 保留 {kept}"
            )

        print(f"\n全部完成。输出目录：{output_dir}")

    finally:
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                print(f"警告：临时文件未能删除：{temp_path}")


if __name__ == "__main__":
    main()

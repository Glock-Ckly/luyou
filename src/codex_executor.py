"""
Codex 执行器 — 将 DeepSeek 规划交给 Codex CLI 非交互执行。

仅负责 subprocess 调用，不包含业务逻辑。
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CodexResult:
    success: bool
    output: str
    workdir: str
    exit_code: int
    output_file: str | None = None
    error: str | None = None


def codex_available() -> bool:
    return shutil.which("codex") is not None


async def run_codex(
    prompt: str,
    *,
    workdir: str | Path,
    timeout: float = 600.0,
    skip_git_check: bool = True,
) -> CodexResult:
    """非交互调用 `codex exec`，返回 stdout + 最后消息文件内容。"""
    work = Path(workdir).resolve()
    if not work.is_dir():
        return CodexResult(
            success=False,
            output="",
            workdir=str(work),
            exit_code=-1,
            error=f"工作目录不存在: {work}",
        )

    if not codex_available():
        return CodexResult(
            success=False,
            output="",
            workdir=str(work),
            exit_code=-1,
            error="未找到 codex CLI，请确认已安装并在 PATH 中",
        )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        out_path = f.name

    cmd = [
        "codex", "exec",
        "-C", str(work),
        "-o", out_path,
    ]
    if skip_git_check:
        cmd.append("--skip-git-repo-check")

    cmd.append(prompt)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(work),
        )
        stdout_b, stderr_b = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")

        last_msg = ""
        out_file = Path(out_path)
        if out_file.is_file():
            last_msg = out_file.read_text(encoding="utf-8", errors="replace")
            out_file.unlink(missing_ok=True)

        combined = last_msg.strip() or stdout.strip()
        if stderr.strip() and not combined:
            combined = stderr.strip()

        ok = proc.returncode == 0 and bool(combined)
        return CodexResult(
            success=ok,
            output=combined,
            workdir=str(work),
            exit_code=proc.returncode or 0,
            output_file=out_path if last_msg else None,
            error=None if ok else (stderr.strip() or f"exit {proc.returncode}"),
        )
    except asyncio.TimeoutError:
        return CodexResult(
            success=False,
            output="",
            workdir=str(work),
            exit_code=-2,
            error=f"Codex 执行超时 ({timeout}s)",
        )
    except Exception as e:
        return CodexResult(
            success=False,
            output="",
            workdir=str(work),
            exit_code=-1,
            error=str(e),
        )


if __name__ == "__main__":
    import sys

    wd = sys.argv[1] if len(sys.argv) > 1 else "."
    p = sys.argv[2] if len(sys.argv) > 2 else "echo hello"
    print("codex available:", codex_available())
    r = asyncio.run(run_codex(p, workdir=wd, timeout=30))
    print("success:", r.success)
    print("output:", r.output[:500] if r.output else r.error)

#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

# 1) 参数校验
if [ $# -ne 2 ]; then
  echo "Usage: $0 <input_file> <output_directory>"
  exit 1
fi

INPUT_FILE="$1"
OUTPUT_DIR="$2"

# 2) 输入输出检查
if [ ! -f "$INPUT_FILE" ]; then
  echo "Error: Input file $INPUT_FILE does not exist"
  exit 1
fi
mkdir -p "$OUTPUT_DIR"

# 3) 统一转绝对路径（先得到 POSIX 绝对路径，再转 Windows 路径）
to_posix_abs() {
  # 传入可能是相对路径/./..；用 dirname/basename + pwd -P 组合成绝对 POSIX 路径
  local p="$1"
  local dir base
  dir="$(dirname -- "$p")"
  base="$(basename -- "$p")"
  ( cd "$dir" >/dev/null 2>&1 && printf '%s/%s\n' "$(pwd -P)" "$base" )
}

to_win_abs() {
  local p_abs="$1"   # 必须是 POSIX 绝对路径：/e/xxx 或 /c/xxx
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -w -- "$p_abs"
  else
    # 兜底：把 /e/ 转成 e:/ 再把 / 换成 \
    local win
    win="$(echo "$p_abs" | sed -E 's#^/([a-zA-Z])/#\1:/#')"
    echo "${win//\//\\}"
  fi
}

INPUT_POSIX_ABS="$(to_posix_abs "$INPUT_FILE")"
OUTPUT_POSIX_ABS="$(to_posix_abs "$OUTPUT_DIR")"

INPUT_WIN_ABS="$(to_win_abs "$INPUT_POSIX_ABS")"
OUTPUT_WIN_ABS="$(to_win_abs "$OUTPUT_POSIX_ABS")"

echo "==> Mounting:"
echo "    host input : $INPUT_WIN_ABS  ->  /data/input/urls.txt (ro)"
echo "    host output: $OUTPUT_WIN_ABS  ->  /data/output"

# 4) 运行容器（-v 左侧必须是 Windows 绝对路径；右侧固定为容器内路径）
docker run --rm \
  --name http-fetcher \
  -v "$INPUT_WIN_ABS:/data/input/urls.txt:ro" \
  -v "$OUTPUT_WIN_ABS:/data/output" \
  http-fetcher:latest

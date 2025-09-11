# benford/views.py
import os
import uuid
import threading
from typing import List, Dict, Optional

import pandas as pd

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from collections import Counter

from .utils import (
    extract_numbers_with_context_from_file,
    analyze_benford,
)

# 进度表（单进程内存）。生产环境请换 Redis/DB。
_PROGRESS: Dict[str, Dict] = {}
_PROGRESS_LOCK = threading.Lock()

@login_required
def index(request):
    """GET /benford/ → 上传与进度页面"""
    return render(request, "benford/index.html")


def _safe_unique_path(base_dir: str, filename: str) -> str:
    """
    在 base_dir 下为 filename 生成不重复的保存路径。
    同名时自动添加短UUID前缀。
    """
    name = os.path.basename(filename)
    dst = os.path.join(base_dir, name)
    if not os.path.exists(dst):
        return dst
    stem, ext = os.path.splitext(name)
    return os.path.join(base_dir, f"{stem}_{uuid.uuid4().hex[:8]}{ext}")


def _save_all_files_to_disk(job_id: str, uploaded_files) -> List[str]:
    """
    在主线程里把所有上传文件保存到磁盘，并返回保存后的绝对路径列表。
    这样后台线程只读磁盘文件，避免“closed file”问题。
    """
    base_dir = os.path.join(settings.MEDIA_ROOT, "benford_uploads", job_id)
    os.makedirs(base_dir, exist_ok=True)

    saved_paths: List[str] = []
    for f in uploaded_files:
        dst = _safe_unique_path(base_dir, f.name)
        with open(dst, "wb") as out:
            for chunk in f.chunks():
                out.write(chunk)
        saved_paths.append(dst)
    return saved_paths


def _export_result_files(result: Dict, job_id: str, failed_files: Optional[List[str]] = None) -> Dict[str, str]:
    save_dir = os.path.join(settings.MEDIA_ROOT, "benford_results")
    os.makedirs(save_dir, exist_ok=True)
    excel_url = None
    try:
        excel_path = os.path.join(save_dir, f"{job_id}.xlsx")
        with pd.ExcelWriter(excel_path) as writer:
            rows = [
                {
                    "digit": d,
                    "count": result["first_digit_counts"].get(d, 0),
                    "actual_pct": result["actual"].get(d, 0),
                    "expected_pct": result["expected"].get(d, 0),
                }
                for d in range(1, 10)
            ]
            pd.DataFrame(rows).to_excel(writer, index=False, sheet_name="digits")
            for d, dist in result.get("digit_length_distribution", {}).items():
                pd.DataFrame(dist, columns=["length", "count"]).to_excel(
                    writer, index=False, sheet_name=f"{d}_length"
                )
            for d, items in result.get("digit_top_numbers", {}).items():
                pd.DataFrame(items).to_excel(
                    writer, index=False, sheet_name=f"{d}_numbers"
                )
        excel_url = settings.MEDIA_URL + f"benford_results/{job_id}.xlsx"
    except Exception:
        pass
    # PDF 导出功能暂时关闭
    return {"excel_url": excel_url}


@login_required
def upload(request):
    """
    POST /benford/upload/ → 接收文件并启动后台线程处理
    返回 {job_id: "..."}
    """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    files = request.FILES.getlist("files")
    if not files:
        return JsonResponse({"error": "No files"}, status=400)

    job_id = uuid.uuid4().hex

    # 1) 先把所有上传文件保存到磁盘（主线程完成，避免句柄被关闭）
    try:
        saved_paths = _save_all_files_to_disk(job_id, files)
    except Exception as e:
        return JsonResponse({"error": f"Save failed: {e}"}, status=500)

    # 2) 初始化进度（总步骤 = 可处理文件数 + 1（Benford总体分析））
    total_steps = len(saved_paths) + 1
    with _PROGRESS_LOCK:
        _PROGRESS[job_id] = {
            "status": "in_progress",
            "processed": 0,
            "total": total_steps,
            "result": None,
            "error": None,
            "failed_files": [],   # 记录解析失败的文件
        }

    # 3) 后台线程仅处理磁盘上的文件
    def _worker(paths: List[str], job: str):
        all_numbers: List[str] = []
        number_contexts: List[Dict] = []
        failed: List[str] = []
        digit_file_counts: Dict[int, List[Dict]] = {d: [] for d in range(1, 10)}

        try:
            for p in paths:
                try:
                    num_ctxs = extract_numbers_with_context_from_file(p)
                    nums = [r["number"] for r in num_ctxs]
                    basename = os.path.basename(p)
                    if nums:
                        all_numbers.extend(nums)
                        number_contexts.extend(num_ctxs)
                        fd_counter = Counter(
                            s[0]
                            for s in nums
                            if s and s[0].isdigit() and s[0] != "0"
                        )
                        for d, cnt in fd_counter.items():
                            digit_file_counts[int(d)].append({"file": basename, "count": cnt})
                except Exception as fe:
                    failed.append(f"{os.path.basename(p)}: {fe}")
                finally:
                    with _PROGRESS_LOCK:
                        _PROGRESS[job]["processed"] += 1

            # Benford 分析（得到实际/期望分布与结论）
            actual, expected, conclusion = analyze_benford(all_numbers)

            # 额外统计：总量、首位数字计数、卡方统计量（df=8）
            first_digits = [s[0] for s in all_numbers if s and s[0].isdigit() and s[0] != "0"]
            total_fd = len(first_digits)
            fd_counts = {d: 0 for d in range(1, 10)}
            for ch in first_digits:
                d = int(ch)
                if 1 <= d <= 9:
                    fd_counts[d] += 1

            chi_square = None
            if total_fd and expected:
                chi_square = 0.0
                for d in range(1, 10):
                    exp_pct = expected.get(d, 0.0)
                    exp_cnt = exp_pct * total_fd / 100.0
                    obs = fd_counts.get(d, 0)
                    if exp_cnt > 0:
                        chi_square += (obs - exp_cnt) ** 2 / exp_cnt
                # 这里只返回统计量值（自由度 df=8），若要 p 值可引入 scipy 计算

            top_files_by_digit: Dict[int, List[Dict]] = {}
            digit_length_distribution: Dict[int, List] = {}
            digit_top_numbers: Dict[int, List[Dict]] = {}
            digits_exceed: List[int] = []
            if actual and expected:
                digits_exceed = [
                    d for d in range(1, 10) if actual.get(d, 0) > expected.get(d, 0)
                ]
                for d in digits_exceed:
                    files = sorted(
                        digit_file_counts.get(d, []),
                        key=lambda x: x["count"],
                        reverse=True,
                    )
                    top_files_by_digit[d] = files[:20]

                    numbers_d = [n for n in all_numbers if n.startswith(str(d))]
                    length_counts = Counter(len(n) for n in numbers_d)
                    digit_length_distribution[d] = length_counts.most_common(5)

                    num_counter = Counter(n for n in numbers_d)
                    top_nums = []
                    for num, cnt in num_counter.most_common(5):
                        ctx = next(
                            (c["context"] for c in number_contexts if c["number"] == num),
                            "",
                        )
                        top_nums.append({"number": num, "count": cnt, "context": ctx})
                    digit_top_numbers[d] = top_nums

            with _PROGRESS_LOCK:
                _PROGRESS[job]["processed"] += 1  # Benford 总结步骤
                _PROGRESS[job]["status"] = "done"
                result = {
                    "actual": actual,
                    "expected": expected,
                    "conclusion": conclusion,
                    "total_numbers": len(all_numbers),
                    "first_digit_counts": fd_counts,
                    "chi_square": chi_square,
                    "top_files_by_digit": top_files_by_digit,
                    "global_sample": all_numbers[:50],  # 全局前 50 个样本
                    "digit_length_distribution": digit_length_distribution,
                    "digit_top_numbers": digit_top_numbers,
                }
                file_urls = _export_result_files(result, job, failed)
                result.update(file_urls)
                _PROGRESS[job]["result"] = result
                _PROGRESS[job]["failed_files"] = failed

        except Exception as e:
            with _PROGRESS_LOCK:
                _PROGRESS[job]["status"] = "error"
                _PROGRESS[job]["error"] = str(e)
                _PROGRESS[job]["failed_files"] = failed

    threading.Thread(target=_worker, args=(saved_paths, job_id), daemon=True).start()
    return JsonResponse({"job_id": job_id})


@login_required
def status(request, job_id: str):
    """
    GET /benford/status/<job_id>/ → 返回进度与结果
    {status, processed, total, result?, failed_files?, error?}
    """
    with _PROGRESS_LOCK:
        data = _PROGRESS.get(job_id)
        if not data:
            return JsonResponse({"error": "job not found"}, status=404)
        resp = {
            "status": data["status"],
            "processed": data["processed"],
            "total": data["total"],
        }
        if data.get("failed_files"):
            resp["failed_files"] = data["failed_files"]
        if data["status"] == "done":
            resp["result"] = data["result"]
        if data.get("error"):
            resp["error"] = data["error"]

    return JsonResponse(resp)

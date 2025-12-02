#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask UI for Farsi Kinetic Typography Video Generator
-----------------------------------------------------
Features:
- Projects: each with an audio + base video.
- Jobs: render requests for projects, queued and processed sequentially.
- Media: rendered output files.
- Simple SQLite database via SQLAlchemy.
- Background worker thread + progress percentage per job.

You can freely edit / extend this code.
"""

import os
import threading
import queue
import uuid
import datetime

from flask import (
    Flask, render_template, request, redirect,
    url_for, send_from_directory, flash, jsonify
)

from sqlalchemy.orm import Session

from models import (
    engine, Base, Project, Job, Media,
    get_session
)
import motion_pipeline  # local pipeline wrapper

# -------------------------------------------------------------------
# Basic paths
# -------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -------------------------------------------------------------------
# Flask app
# -------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = "please-change-this-secret"

# ایجاد جداول دیتابیس در صورت عدم وجود
Base.metadata.create_all(bind=engine)

# -------------------------------------------------------------------
# Job Queue in memory (only for ordering); Job rows in DB
# -------------------------------------------------------------------
JOB_QUEUE: "queue.Queue[int]" = queue.Queue()

def enqueue_job(project_id: int, audio_path: str, video_path: str) -> int:
    """
    Create a Job row in DB, enqueue its ID for background processing,
    and return the Job ID.
    """
    db: Session = get_session()
    try:
        job = Job(
            uuid=str(uuid.uuid4())[:8],
            project_id=project_id,
            audio_path=audio_path,
            video_path=video_path,
            status="queued",
            progress=0,
            message="در صف انتظار...",
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        JOB_QUEUE.put(job.id)
        return job.id
    finally:
        db.close()

# -------------------------------------------------------------------
# Background worker
# -------------------------------------------------------------------
def worker_loop():
    """
    Background worker:
    Takes Job IDs from JOB_QUEUE and runs them sequentially.
    """
    while True:
        job_id = JOB_QUEUE.get()  # block until a job is available
        db: Session = get_session()
        try:
            job: Job = db.get(Job, job_id)
            if not job:
                JOB_QUEUE.task_done()
                db.close()
                continue

            job.status = "running"
            job.progress = 5
            job.message = "شروع پردازش..."
            job.updated_at = datetime.datetime.now()
            db.commit()

            def progress_callback(percent: int, msg: str):
                # این تابع از داخل motion_pipeline فراخوانی می‌شود
                j = db.get(Job, job_id)
                if not j:
                    return
                j.progress = max(0, min(100, int(percent)))
                j.message = msg
                j.updated_at = datetime.datetime.now()
                db.commit()

            # اجرای pipeline
            try:
                output_path = motion_pipeline.process_job(
                    audio_path=job.audio_path,
                    video_path=job.video_path,
                    output_dir=OUTPUT_DIR,
                    progress_callback=progress_callback,
                    quality="h",
                )
                # ذخیره Media
                media = Media(
                    project_id=job.project_id,
                    job_id=job.id,
                    file_path=output_path,
                    media_type="video",
                    created_at=datetime.datetime.now(),
                )
                db.add(media)

                job.status = "done"
                job.progress = 100
                job.message = "تمام شد ✅"
                job.output_path = output_path
                job.updated_at = datetime.datetime.now()
                db.commit()
            except Exception as e:
                job.status = "error"
                job.progress = 0
                job.message = "خطا در اجرای جاب"
                job.error = str(e)
                job.updated_at = datetime.datetime.now()
                db.commit()

        finally:
            JOB_QUEUE.task_done()
            db.close()

# Start background worker thread
worker_thread = threading.Thread(target=worker_loop, daemon=True)
worker_thread.start()

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def _save_upload(file_obj, subdir: str) -> str:
    """
    Save an uploaded file into uploads/subdir and return full path.
    """
    if not file_obj or file_obj.filename == "":
        return ""
    folder = os.path.join(UPLOAD_DIR, subdir)
    os.makedirs(folder, exist_ok=True)
    filename = file_obj.filename
    path = os.path.join(folder, filename)
    file_obj.save(path)
    return path

# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------
@app.route("/")
def root():
    # داشبورد ساده → پروژه‌ها
    return redirect(url_for("projects_list"))

# ---------- Projects ----------
@app.route("/projects", methods=["GET", "POST"])
def projects_list():
    """
    لیست پروژه‌ها + فرم ساخت پروژه جدید (به همراه جاب اول).
    """
    db: Session = get_session()
    try:
        if request.method == "POST":
            name = request.form.get("name") or "پروژه بدون نام"
            audio_file = request.files.get("audio")
            video_file = request.files.get("video")

            if not audio_file or audio_file.filename == "":
                flash("فایل صوتی را انتخاب کنید.", "error")
                return redirect(url_for("projects_list"))
            if not video_file or video_file.filename == "":
                flash("فایل ویدیو را انتخاب کنید.", "error")
                return redirect(url_for("projects_list"))

            # ذخیره فایل‌ها
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            subdir = f"project_{stamp}"
            audio_path = _save_upload(audio_file, subdir)
            video_path = _save_upload(video_file, subdir)

            # ساخت پروژه
            project = Project(
                name=name,
                audio_path=audio_path,
                video_path=video_path,
                created_at=datetime.datetime.now(),
            )
            db.add(project)
            db.commit()
            db.refresh(project)

            # ایجاد اولین جاب برای این پروژه
            job_id = enqueue_job(project_id=project.id,
                                 audio_path=audio_path,
                                 video_path=video_path)

            flash(f"پروژه '{project.name}' ساخته شد و جاب #{job_id} به صف اضافه شد.", "success")
            return redirect(url_for("project_detail", project_id=project.id))

        # GET → لیست پروژه‌ها
        projects = db.query(Project).order_by(Project.created_at.desc()).all()
        return render_template("projects.html", projects=projects)
    finally:
        db.close()

@app.route("/projects/<int:project_id>")
def project_detail(project_id: int):
    """
    جزئیات یک پروژه: نمایش فایل‌ها، جاب‌ها و مدیاهای مربوطه.
    """
    db: Session = get_session()
    try:
        project = db.get(Project, project_id)
        if not project:
            flash("پروژه پیدا نشد.", "error")
            return redirect(url_for("projects_list"))
        jobs = db.query(Job).filter(Job.project_id == project_id).order_by(Job.created_at.desc()).all()
        medias = db.query(Media).filter(Media.project_id == project_id).order_by(Media.created_at.desc()).all()
        return render_template("project_detail.html", project=project, jobs=jobs, medias=medias)
    finally:
        db.close()

@app.route("/projects/<int:project_id>/new-job", methods=["POST"])
def project_new_job(project_id: int):
    """
    ایجاد یک جاب جدید برای پروژه موجود (مثلاً بعد از تغییر motion.py).
    """
    db: Session = get_session()
    try:
        project = db.get(Project, project_id)
        if not project:
            flash("پروژه پیدا نشد.", "error")
            return redirect(url_for("projects_list"))

        job_id = enqueue_job(
            project_id=project.id,
            audio_path=project.audio_path,
            video_path=project.video_path,
        )
        flash(f"جاب جدید #{job_id} برای این پروژه ساخته شد.", "success")
        return redirect(url_for("jobs_detail", job_id=job_id))
    finally:
        db.close()

# ---------- Jobs ----------
@app.route("/jobs")
def jobs_list():
    """
    لیست تمام جاب‌ها.
    """
    db: Session = get_session()
    try:
        jobs = db.query(Job).order_by(Job.created_at.desc()).limit(200).all()
        return render_template("jobs.html", jobs=jobs)
    finally:
        db.close()

@app.route("/jobs/<int:job_id>")
def jobs_detail(job_id: int):
    """
    صفحه‌ی وضعیت یک جاب.
    """
    db: Session = get_session()
    try:
        job = db.get(Job, job_id)
        if not job:
            flash("جاب پیدا نشد.", "error")
            return redirect(url_for("jobs_list"))
        return render_template("job_detail.html", job=job)
    finally:
        db.close()

@app.route("/jobs/<int:job_id>/json")
def jobs_status_json(job_id: int):
    """
    JSON status برای Ajax.
    """
    db: Session = get_session()
    try:
        job = db.get(Job, job_id)
        if not job:
            return jsonify({"error": "job not found"}), 404
        return jsonify(job.to_dict())
    finally:
        db.close()

# ---------- Media ----------
@app.route("/media")
def media_list():
    """
    لیست فایل‌های خروجی (مدیا).
    """
    db: Session = get_session()
    try:
        medias = db.query(Media).order_by(Media.created_at.desc()).all()
        return render_template("media.html", medias=medias)
    finally:
        db.close()

@app.route("/media/file/<int:media_id>")
def media_file(media_id: int):
    """
    سرو فایل مدیا (ویدیو خروجی).
    """
    db: Session = get_session()
    try:
        media = db.get(Media, media_id)
        if not media:
            flash("مدیا پیدا نشد.", "error")
            return redirect(url_for("media_list"))

        directory = os.path.dirname(media.file_path)
        fname = os.path.basename(media.file_path)
        return send_from_directory(directory, fname, as_attachment=False)
    finally:
        db.close()

# -------------------------------------------------------------------
# Run
# -------------------------------------------------------------------
if __name__ == "__main__":
    # برای محیط توسعه
    app.run(host="0.0.0.0", port=5000, debug=True)

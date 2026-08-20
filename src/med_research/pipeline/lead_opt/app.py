import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from . import jobs, pipeline, utils

app = Flask(
    __name__,
    template_folder=Path(__file__).parent / "templates",
    static_folder=Path(__file__).parent / "static",
)

# In‑memory job store (job_id -> {'status': 'pending'/'running'/'done'/'error', 'result': None})
job_store = {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    # Accept CSV, JSON or raw SMILES text
    file = request.files.get("file")
    raw_text = request.form.get("smiles_text")
    if not file and not raw_text:
        return jsonify({"error": "No file or SMILES text provided"}), 400
    # Read content
    if file:
        content = file.read().decode("utf-8")
        filename = file.filename.lower()
        if filename.endswith(".csv"):
            df = utils.parse_csv(content)
        elif filename.endswith(".json"):
            df = utils.parse_json(content)
        else:
            return jsonify({"error": "Unsupported file type"}), 400
    else:
        df = utils.parse_smiles_text(raw_text)
    # Create job entry
    job_id = str(uuid.uuid4())
    job_store[job_id] = {"status": "pending", "result": None}

    # Dispatch async processing
    def run_job():
        job_store[job_id]["status"] = "running"
        try:
            result_df = pipeline.process_dataframe(df)
            csv_path = utils.save_result_csv(result_df, job_id)
            job_store[job_id]["result"] = {
                "csv_path": csv_path,
                "data": result_df.to_dict(orient="records"),
            }
            job_store[job_id]["status"] = "done"
        except Exception as e:
            job_store[job_id]["status"] = "error"
            job_store[job_id]["error"] = str(e)

    jobs.submit_job(run_job)
    return jsonify({"job_id": job_id}), 202


@app.route("/status/<job_id>", methods=["GET"])
def status(job_id):
    job = job_store.get(job_id)
    if not job:
        return jsonify({"error": "Invalid job id"}), 404
    return jsonify({"status": job["status"]})


@app.route("/results/<job_id>", methods=["GET"])
def results(job_id):
    job = job_store.get(job_id)
    if not job:
        return jsonify({"error": "Invalid job id"}), 404
    if job["status"] != "done":
        return jsonify({"error": "Job not completed"}), 400
    # Return JSON data and allow CSV download via query param
    if request.args.get("download") == "csv":
        return send_file(
            job["result"]["csv_path"], as_attachment=True, download_name="lead_opt_results.csv"
        )
    return jsonify(job["result"]["data"])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

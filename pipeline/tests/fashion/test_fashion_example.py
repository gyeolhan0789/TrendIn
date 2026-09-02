from trendin.fashion import example


def test_submit_job_encodes_submission_time():
    assert example.submit_job(now=1_700_000_000) == "demo-1700000000"


def test_job_is_not_done_before_duration():
    job_id = example.submit_job(now=1_000)
    assert example.job_is_done(job_id, now=1_000 + example.JOB_DURATION_SECONDS - 1) is False


def test_job_is_done_after_duration():
    job_id = example.submit_job(now=1_000)
    assert example.job_is_done(job_id, now=1_000 + example.JOB_DURATION_SECONDS) is True


def test_unknown_job_id_is_rejected():
    try:
        example.job_is_done("batch_abc", now=0)
    except ValueError:
        return
    raise AssertionError("ValueError 가 나야 한다")

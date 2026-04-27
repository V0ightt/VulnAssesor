import subprocess


def healthcheck(request):
    return {"status": "ok"}


def dangerous_call(request):
    user_cmd = request.GET["cmd"]
    return subprocess.run(user_cmd, shell=True, capture_output=True, text=True)

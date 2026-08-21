"""Document local API entry points. Example · not clinical advice."""


def main() -> None:
    print("Start: nosograph serve --host 127.0.0.1 --port 8000")
    print("OpenAPI UI:  http://127.0.0.1:8000/api/docs")
    print("Health:      http://127.0.0.1:8000/api/health")
    print("Compare:     POST /api/v1/nosograph/compare")
    print("Auth: local DEBUG=true typically; production requires API_KEY.")


if __name__ == "__main__":
    main()

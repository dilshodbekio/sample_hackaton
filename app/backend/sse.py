import json


def format_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class SSEParser:
    """Oqimdan kelgan bo'laklarni yig'ib, to'liq voqealarga ajratadi.

    Bitta voqea bir necha bo'lakka bo'linib kelishi mumkin, shuning uchun
    bufer bo'sh qator (\\n\\n) kelguncha yig'iladi.
    """

    def __init__(self) -> None:
        self._buffer = ""

    def feed(self, chunk: str) -> list[tuple[str, dict]]:
        self._buffer += chunk.replace("\r\n", "\n")
        events = []
        while "\n\n" in self._buffer:
            raw, self._buffer = self._buffer.split("\n\n", 1)
            event, data_lines = "message", []
            for line in raw.split("\n"):
                if line.startswith("event:"):
                    event = line[6:].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
            if not data_lines:
                continue
            try:
                data = json.loads("\n".join(data_lines))
            except json.JSONDecodeError:
                data = {}
            events.append((event, data))
        return events

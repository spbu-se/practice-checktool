FROM python:3.12-alpine

RUN apk add --no-cache git jq bash curl libstdc++ coreutils
RUN addgroup -S opencode
RUN adduser -S -D -h /home/opencode -G opencode opencode

USER opencode
ENV HOME /home/opencode
ENV PATH "${HOME}/.opencode/bin:${PATH}"

WORKDIR /home/opencode

RUN curl -fsSL https://opencode.ai/install | bash
COPY --chown=opencode:opencode pyproject.toml .
COPY --chown=opencode:opencode pg-cli.py .
COPY --chown=opencode:opencode opencode/agents opencode/agents

RUN pip install --no-cache-dir -e .

ENTRYPOINT ["python", "pg-cli.py"]

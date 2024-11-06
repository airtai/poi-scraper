FROM python:3.11

WORKDIR /app

COPY poi_scraper /app/poi_scraper

COPY pyproject.toml README.md docker/run_fastagency.sh /app/

RUN pip install --upgrade pip && pip install --no-cache-dir -e "."

RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app

USER appuser

EXPOSE 8000 8008 8888

CMD ["/app/run_fastagency.sh"]

# Run the build command from root of fastagency repo
# docker build -t deploy_fastagency -f docker/Dockerfile .

# Run the container

# docker run --rm -d --name deploy_fastagency -e OPENAI_API_KEY=$OPENAI_API_KEY  -p 8888:8888  deploy_fastagency

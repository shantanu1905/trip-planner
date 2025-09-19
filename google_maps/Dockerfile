FROM python:3.11-slim


# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive \
PYTHONDONTWRITEBYTECODE=1 \
PYTHONUNBUFFERED=1 \
HEADLESS=true \
CACHE_DIR=/app/data


WORKDIR /app


# System deps for Chrome
RUN apt-get update && apt-get install -y --no-install-recommends \
curl ca-certificates gnupg apt-transport-https unzip \
fonts-liberation libasound2 libatk1.0-0 libatk-bridge2.0-0 \
libc6 libdrm2 libgbm1 libgtk-3-0 libnspr4 libnss3 libx11-6 \
libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 libxdamage1 \
libxext6 libxfixes3 libxi6 libxrandr2 libxrender1 libxss1 \
libxtst6 xdg-utils \
&& rm -rf /var/lib/apt/lists/*


# Install Google Chrome Stable
RUN mkdir -p /etc/apt/keyrings \
&& curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg \
&& echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
&& apt-get update && apt-get install -y --no-install-recommends google-chrome-stable \
&& rm -rf /var/lib/apt/lists/*


# App deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt


# App code
COPY . .


# Create cache dir
RUN mkdir -p ${CACHE_DIR}


EXPOSE 8000


CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
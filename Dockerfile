FROM mcr.microsoft.com/playwright:v1.61.1-jammy

WORKDIR /app

# poppler-utils fornece pdftoppm para converter PDF em imagem PNG
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils && rm -rf /var/lib/apt/lists/*

COPY package*.json ./
RUN npm install

COPY tsconfig.json ./
COPY src/ ./src/
RUN npm run build

COPY . .

CMD ["node", "dist/index.js"]

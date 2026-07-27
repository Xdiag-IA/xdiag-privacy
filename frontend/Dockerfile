# Frontend image. Single stage; we run Vite's preview server in production
# so the container stays lightweight and there is no need for nginx. For a
# real deployment, swap to a multi stage build that emits static assets and
# serves them with nginx or caddy.

FROM node:20-alpine

ENV NODE_ENV=development

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 5173 4173

# Default to the dev server so HMR works inside the container; switch to
# `npm run build && npm run preview` for a production style serve.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

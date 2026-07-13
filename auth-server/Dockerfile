FROM node:22-slim

ENV NODE_ENV=production

WORKDIR /app

RUN groupadd --system kquant \
    && useradd --system --gid kquant --no-create-home kquant

COPY auth-server/package.json auth-server/package-lock.json* /app/
RUN npm install --omit=dev && npm cache clean --force

COPY --chown=kquant:kquant auth-server/src /app/src

RUN chmod -R a-w /app

USER kquant
EXPOSE 4000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:4000/auth/health').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"

CMD ["node", "src/index.js"]

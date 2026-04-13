#!/bin/bash

# Быстрая настройка CI/CD для microk8s
# Запустите этот скрипт на microk8s хосте

set -e

echo "=========================================="
echo "itemstock_mvp - Настройка для microk8s"
echo "=========================================="
echo ""

# Проверка microk8s
if ! command -v microk8s &> /dev/null; then
    echo "❌ microk8s не установлен"
    echo "Установите: sudo snap install microk8s --classic"
    exit 1
fi

echo "✓ microk8s найден"

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен"
    exit 1
fi

echo "✓ Docker найден"

# Создание namespace
echo ""
echo "📦 Создание namespace itemstock..."
microk8s kubectl create namespace itemstock --dry-run=client -o yaml | microk8s kubectl apply -f -

# Включение необходимых addons
echo ""
echo "🔧 Включение microk8s addons..."
microk8s enable dns 2>/dev/null || true
microk8s enable storage 2>/dev/null || true
microk8s enable ingress 2>/dev/null || true

echo "✓ Хранилище включено (используется встроенный microk8s-hostpath)"

# Генерация SSH ключа для GitHub Actions (опционально)
echo ""
echo "🔑 SSH ключи:"
SSH_KEY_PATH="$HOME/.ssh/itemstock_deploy"
if [ ! -f "$SSH_KEY_PATH" ]; then
    echo "📝 Генерирую SSH ключ для развертывания..."
    ssh-keygen -t ed25519 -f "$SSH_KEY_PATH" -N "" -C "itemstock-deploy"
    echo "✓ SSH ключ создан: $SSH_KEY_PATH"
else
    echo "✓ SSH ключ уже существует: $SSH_KEY_PATH"
fi

echo ""
echo "=========================================="
echo "✅ Базовая настройка завершена!"
echo "=========================================="
echo ""
echo "📋 Что дальше:"
echo ""
echo "1️⃣  Получите параметры для GitHub Secrets:"
echo ""
echo "   MICROK8S_HOST:"
echo "     Команда: hostname -I"
echo "     или используйте IP адрес вашего сервера"
echo ""
echo "   MICROK8S_USER:"
echo "     Текущий пользователь: $(whoami)"
echo ""
echo "   MICROK8S_KEY (только если используете deploy.yml с GHCR):"
cat "$SSH_KEY_PATH" | base64
echo ""
echo "2️⃣  Откройте GitHub → Settings → Secrets and variables → Actions"
echo ""
echo "3️⃣  Добавьте следующие secrets для deploy-simple.yml:"
echo "   - MICROK8S_HOST (IP вашего сервера)"
echo "   - MICROK8S_USER (SSH пользователь)"
echo "   - MICROK8S_KEY (содержимое ~/.ssh/id_rsa, закодировано в base64)"
echo ""
echo "4️⃣  Сделайте push в GitHub:"
echo "   git push origin main"
echo ""
echo "📖 Для подробных инструкций смотрите: DEPLOYMENT.md"
echo ""

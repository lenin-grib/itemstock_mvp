# 🚀 Быстрая шпаргалка - itemstock_mvp на microk8s

## 📌 Первоначальная настройка (на microk8s хосте)

```bash
# 1. Сделайте скрипты исполняемыми
chmod +x k8s/quick-setup.sh k8s/setup.sh

# 2. Запустите быструю настройку
./k8s/quick-setup.sh

# 3. Добавьте SSH ключ в GitHub (Settings → Deploy keys)
cat ~/.ssh/itemstock_deploy.pub
```

## 📋 Настройка GitHub Secrets

В репозитории перейдите: **Settings → Secrets and variables → Actions**

Добавьте:

```
MICROK8S_HOST = <IP_вашего_сервера>
MICROK8S_USER = <ваше_имя_пользователя>
MICROK8S_KEY = <содержимое_~/.ssh/id_rsa_в_base64>
```

Получить base64 SSH ключа:

```bash
cat ~/.ssh/id_rsa | base64 -w 0
```

## 🔄 Развертывание

### Автоматически (при push в main/develop)

```bash
git commit -m "your message"
git push origin main
```

### Вручную (на microk8s хосте)

```bash
# Клонируйте репо
git clone https://github.com/lenin-grib/itemstock_mvp.git
cd itemstock_mvp

# Постройте образ
docker build -t itemstock:v1 .

# Примените manifests
microk8s kubectl apply -f k8s/deployment.yaml

# Обновите deployment
microk8s kubectl set image deployment/itemstock-app \
  itemstock=itemstock:v1 -n itemstock
```

## 👀 Мониторинг

```bash
# Статус pods
microk8s kubectl get pods -n itemstock

# Логи приложения (в реальном времени)
microk8s kubectl logs -n itemstock -l app=itemstock -f

# Описание deployment
microk8s kubectl describe deployment itemstock-app -n itemstock

# Все ресурсы в namespace
microk8s kubectl get all -n itemstock

# События
microk8s kubectl get events -n itemstock
```

## 🌐 Доступ к приложению

```bash
# 1. Узнайте IP сервиса
microk8s kubectl get svc -n itemstock

# 2. Откройте в браузере
# http://<SERVICE_IP>:80
# или
# http://localhost:8501 (если на локальной машине)
```

## 🔧 Troubleshooting

### Pods не запускаются

```bash
# Посмотрите описание pod
microk8s kubectl describe pod <pod_name> -n itemstock

# Посмотрите логи
microk8s kubectl logs <pod_name> -n itemstock
```

### Образ не скачивается

```bash
# Проверьте доступные образы
docker image ls

# Пересоздайте образ
docker build -t itemstock:latest .
```

### Нужно перезапустить deployment

```bash
microk8s kubectl rollout restart deployment/itemstock-app -n itemstock
```

### Удалить всё и начать заново

```bash
microk8s kubectl delete namespace itemstock
microk8s kubectl apply -f k8s/deployment.yaml
```

## 📊 Используемые workflow

- **deploy.yml** - с GitHub Container Registry (GHCR) - для публичного registry
- **deploy-simple.yml** - локальная сборка на microk8s хосте (рекомендуется для локального сервера)

## 💡 Советы

1. Используйте `deploy-simple.yml` для локальных microk8s серверов
2. Образ автоматически пересобирается при каждом push
3. Приложение автоматически перезапускается при обновлении
4. Данные сохраняются в PersistentVolume

## 📞 Полезные команды

```bash
# Скопировать файл из pod
microk8s kubectl cp itemstock/itemstock-app-xxx:/app/data/file.db ./file.db

# Выполнить команду в pod
microk8s kubectl exec -it <pod_name> -n itemstock -- bash

# Посмотреть переменные окружения pod
microk8s kubectl exec <pod_name> -n itemstock -- env
```

# CI/CD Pipeline для itemstock_mvp на microk8s

Этот документ описывает процесс настройки автоматической сборки и развертывания приложения на microk8s сервер при каждом коммите в GitHub.

## 📋 Компоненты

### 1. Docker образ (`Dockerfile`)

- Базовый образ: `python:3.11-slim`
- Установка зависимостей из `requirements.txt`
- Копирование всех файлов приложения
- Expo порт: 8501 (Streamlit)
- Health check для проверки доступности

### 2. GitHub Actions Workflow (`.github/workflows/deploy.yml`)

Автоматизирует:

- Сборку Docker образа при каждом push в main/develop
- Публикацию образа в GitHub Container Registry (ghcr.io)
- Развертывание на microk8s сервер

### 3. Kubernetes Manifests (`k8s/deployment.yaml`)

Содержит:

- Namespace `itemstock`
- Deployment с 1 репликой
- Service (LoadBalancer)
- Ingress для доступа
- PersistentVolumeClaim для сохранения данных
- ConfigMap с переменными окружения

## 🚀 Инструкция по настройке

### Шаг 1: Подготовка на microk8s сервере

На сервере с microk8s выполните:

```bash
# Сделайте скрипт исполняемым
chmod +x k8s/setup.sh

# Запустите с параметрами GitHub
./k8s/setup.sh YOUR_GITHUB_USERNAME YOUR_GITHUB_TOKEN
```

Где:

- `YOUR_GITHUB_USERNAME` - ваше имя пользователя GitHub
- `YOUR_GITHUB_TOKEN` - Personal Access Token с разрешением `read:packages`

### Шаг 2: Получение kubeconfig

На microk8s сервере выполните:

```bash
# Получить kubeconfig в формате base64
cat /var/snap/microk8s/current/credentials/client.config | base64

# Или если используете ~/.kube/config
cat ~/.kube/config | base64
```

### Шаг 3: Получение SSH приватного ключа

```bash
# Закодировать приватный ключ в base64 (если он не закодирован)
cat ~/.ssh/id_rsa | base64
```

### Шаг 4: Настройка GitHub Secrets

Перейдите в GitHub репозиторий → Settings → Secrets and variables → Actions

Добавьте следующие secrets:

```
MICROK8S_HOST=<IP_или_hostname_вашего_microk8s_сервера>
MICROK8S_USER=<SSH_пользователь>
MICROK8S_KEY=<base64_закодированный_приватный_ключ>
MICROK8S_KUBECONFIG=<base64_закодированный_kubeconfig>
```

### Шаг 5: Применение Kubernetes manifests

На microk8s сервере примените manifest:

```bash
microk8s kubectl apply -f k8s/deployment.yaml
```

Или через GitHub Actions (автоматически при развертывании).

## 📊 Процесс работы

1. **Разработчик** делает push в ветку `main` или `develop`
2. **GitHub Actions**:
   - Собирает Docker образ
   - Публикует в GHCR с тегами (branch, SHA, latest)
   - Запускает развертывание на microk8s
3. **microk8s**:
   - Скачивает новый образ
   - Выполняет rolling update deployment
   - Проверяет health checks
   - Запускает приложение

## 🔍 Мониторинг

### Проверка статуса deployment:

```bash
# Просмотр pods
microk8s kubectl get pods -n itemstock

# Просмотр logs
microk8s kubectl logs -n itemstock -l app=itemstock -f

# Описание deployment
microk8s kubectl describe deployment itemstock-app -n itemstock

# Проверка сервиса
microk8s kubectl get svc -n itemstock
```

### Доступ к приложению:

```bash
# Локально на сервере
curl http://localhost:8501

# Через сервис (если используется LoadBalancer)
curl http://<SERVICE_IP>:80

# Через Ingress (требует настройки DNS)
# http://itemstock.local
```

## 🔧 Troubleshooting

### Образ не скачивается с GHCR

```bash
# Проверить секрет
microk8s kubectl get secrets -n itemstock

# Пересоздать секрет
microk8s kubectl delete secret ghcr-secret -n itemstock
microk8s kubectl create secret docker-registry ghcr-secret \
    --docker-server=ghcr.io \
    --docker-username=<username> \
    --docker-password=<token> \
    -n itemstock
```

### Deployment не обновляется

```bash
# Проверить события
microk8s kubectl describe deployment itemstock-app -n itemstock

# Принудительно перезапустить
microk8s kubectl rollout restart deployment/itemstock-app -n itemstock
```

### Нет доступа к приложению

```bash
# Проверить Pod статус
microk8s kubectl get pod -n itemstock -o wide

# Проверить logs
microk8s kubectl logs <pod-name> -n itemstock

# Проверить сервис
microk8s kubectl get svc -n itemstock
```

## 🛠️ Полезные команды

```bash
# Просмотр всех ресурсов в namespace
microk8s kubectl get all -n itemstock

# Просмотр событий
microk8s kubectl get events -n itemstock

# Проверить образы в кластере
microk8s kubectl get pods -n itemstock -o jsonpath='{.items[*].spec.containers[*].image}'

# Обновить image вручную
microk8s kubectl set image deployment/itemstock-app \
    itemstock=ghcr.io/lenin-grib/itemstock_mvp:main-<short_sha> \
    -n itemstock

# Просмотр логов в реальном времени
microk8s kubectl logs -n itemstock -l app=itemstock -f --all-containers=true
```

## 📝 Примечания

- Образы хранятся в GitHub Container Registry (GHCR)
- Данные приложения сохраняются в PersistentVolume
- Используется rolling update стратегия для zero-downtime развертывания
- Health checks автоматически перезапускают неработающие pods
- Требуется минимум 256MB RAM и 250m CPU на pod

## ❓ Вопросы?

Проверьте логи GitHub Actions в разделе Actions вашего репозитория для детального отслеживания процесса сборки и развертывания.

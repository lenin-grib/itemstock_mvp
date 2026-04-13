# 📦 itemstock_mvp - CI/CD Pipeline для microk8s

Полная настройка автоматической сборки и развертывания приложения на Kubernetes при каждом коммите в GitHub.

## 📚 Документация

- **[QUICKSTART.md](QUICKSTART.md)** - Быстрая шпаргалка для начинающих
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Полная документация с инструкциями

## 🎯 Что было создано

### Контейнеризация

- `Dockerfile` - Docker образ для приложения (Python 3.11, Streamlit)
- `.dockerignore` - Исключение ненужных файлов из образа

### CI/CD Workflows

- `.github/workflows/deploy.yml` - Полный workflow с GitHub Container Registry
- `.github/workflows/deploy-simple.yml` - Упрощенный workflow для локального microk8s (рекомендуется)

### Kubernetes

- `k8s/deployment.yaml` - Manifests для развертывания (Deployment, Service, Ingress, PVC)
- `k8s/setup.sh` - Скрипт настройки на microk8s сервере
- `k8s/quick-setup.sh` - Быстрая автоматическая настройка

## 🚀 Быстрый старт (5 минут)

### На вашем microk8s сервере:

```bash
# 1. Клонируйте репо (если еще не клонировали)
git clone https://github.com/lenin-grib/itemstock_mvp.git
cd itemstock_mvp

# 2. Сделайте скрипты исполняемыми и запустите настройку
chmod +x k8s/quick-setup.sh
./k8s/quick-setup.sh

# 3. Получите SSH ключ для GitHub (скрипт покажет команду)
cat ~/.ssh/itemstock_deploy | base64 -w 0
```

### На GitHub (Settings → Secrets and variables → Actions):

Добавьте secrets:

```
MICROK8S_HOST = <IP_вашего_microk8s_сервера>
MICROK8S_USER = <ваш_ssh_пользователь>
MICROK8S_KEY = <base64_закодированный_приватный_ключ>
```

### Готово! ✅

Теперь при каждом `git push origin main` или `git push origin develop`:

1. GitHub Actions автоматически собирает Docker образ
2. Отправляет на ваш microk8s сервер
3. Перезапускает приложение

## 🏗️ Архитектура

```
GitHub Push
    ↓
GitHub Actions (CI)
    ├─ Checkout code
    ├─ Build Docker image
    └─ Deploy to microk8s
         ↓
    microk8s SSH Deploy
         ├─ Clone repo
         ├─ Build image locally
         ├─ Apply k8s manifests
         └─ Update deployment
              ↓
    Kubernetes Rolling Update
         ├─ Pull new image
         ├─ Start new pod
         ├─ Health check
         └─ Kill old pod
              ↓
    Streamlit App Running ✅
```

## 📊 Компоненты

| Компонент            | Назначение                          |
| -------------------- | ----------------------------------- |
| **Dockerfile**       | Собирает Docker образ с приложением |
| **GitHub Actions**   | Автоматизирует сборку при push      |
| **Deployment**       | Управляет репликами приложения      |
| **Service**          | Предоставляет доступ к приложению   |
| **Ingress**          | Маршрутизирует HTTP трафик          |
| **PersistentVolume** | Сохраняет данные SQLite БД          |
| **ConfigMap**        | Переменные окружения приложения     |

## 🔍 Мониторинг

Проверить статус развертывания:

```bash
# Просмотреть pods
microk8s kubectl get pods -n itemstock

# Смотреть логи в реальном времени
microk8s kubectl logs -n itemstock -l app=itemstock -f

# Полный статус
microk8s kubectl get all -n itemstock
```

## 🔐 Безопасность

- Используется SSH для подключения к microk8s серверу
- GitHub Secrets шифруют все конфиденциальные данные
- Образы хранятся локально (не в публичном registry)
- RBAC можно настроить отдельно при необходимости

## 📝 Переменные окружения

Настраиваются в `k8s/deployment.yaml` (ConfigMap):

```yaml
STREAMLIT_SERVER_PORT: "8501"
STREAMLIT_SERVER_ADDRESS: "0.0.0.0"
STREAMLIT_SERVER_HEADLESS: "true"
```

## 💾 Данные

- SQLite БД хранится в `/app/data/` на PersistentVolume
- Размер PVC: 5Gi (можно изменить в deployment.yaml)
- Storage class: `microk8s-hostpath` (локальное хранилище)

## 🛠️ Настройка ресурсов

В `k8s/deployment.yaml` можно изменить:

```yaml
resources:
  requests:
    memory: "256Mi" # Минимум памяти
    cpu: "250m" # Минимум CPU
  limits:
    memory: "512Mi" # Максимум памяти
    cpu: "500m" # Максимум CPU
```

## ❓ FAQ

### Q: Как посмотреть логи?

A: `microk8s kubectl logs -n itemstock -l app=itemstock -f`

### Q: Как остановить приложение?

A: `microk8s kubectl scale deployment itemstock-app --replicas=0 -n itemstock`

### Q: Как удалить всё?

A: `microk8s kubectl delete namespace itemstock`

### Q: Где хранятся данные?

A: В PersistentVolume, путь: `/var/snap/microk8s/common/default-storage/itemstock-itemstock-data-*`

### Q: Можно ли использовать внешний registry?

A: Да, измените `image` в `k8s/deployment.yaml` и используйте `deploy.yml` вместо `deploy-simple.yml`

## 🚦 Workflow процесс

1. **Разработчик** пушит код в GitHub
2. **GitHub Actions** срабатывает автоматически
3. Workflow SSH подключается к microk8s серверу
4. На сервере собирается Docker образ
5. Kubernetes перезапускает pod с новым образом
6. Старый pod удаляется (rolling update)
7. Новое приложение готово к использованию

## 📞 Поддержка

Для отладки смотрите:

- Логи GitHub Actions: Repository → Actions → Последний run
- Логи microk8s: `microk8s kubectl logs -n itemstock -f`
- События K8s: `microk8s kubectl get events -n itemstock`

## 📄 Файлы проекта

```
itemstock_mvp/
├── Dockerfile                    # Docker образ
├── .dockerignore                 # Исключения для Docker
├── .github/
│   └── workflows/
│       ├── deploy.yml            # Основной workflow (с GHCR)
│       └── deploy-simple.yml     # Упрощенный workflow
├── k8s/
│   ├── deployment.yaml           # K8s manifests
│   ├── setup.sh                  # Полная настройка
│   └── quick-setup.sh            # Быстрая настройка
├── DEPLOYMENT.md                 # Полная документация
├── QUICKSTART.md                 # Быстрая шпаргалка
├── app.py                        # Streamlit приложение
├── requirements.txt              # Python зависимости
└── ...                           # Остальные файлы приложения
```

---

**Готово к развертыванию!** 🎉

Следуйте инструкциям в [QUICKSTART.md](QUICKSTART.md) для быстрого старта.

# 📂 Структура проекта itemstock_mvp после настройки CI/CD

```
itemstock_mvp/
│
├── 📋 ОСНОВНЫЕ ФАЙЛЫ ПРИЛОЖЕНИЯ
│   ├── app.py                          # Главное Streamlit приложение
│   ├── parser.py                       # Парсер файлов
│   ├── forecast.py                     # Прогнозирование
│   ├── ideal_stock.py                  # Расчет идеального запаса
│   ├── supplier_service.py             # Сервис поставщиков
│   ├── cache_service.py                # Кэширование
│   ├── database.py                     # Модели БД
│   ├── db_utils.py                     # Утилиты БД
│   ├── utils.py                        # Общие утилиты
│   ├── catalog.py                      # Каталог товаров
│   ├── requirements.txt                # Python зависимости
│   └── .gitignore                      # Git исключения
│
├── 🐳 DOCKER & КОНТЕЙНЕРИЗАЦИЯ
│   ├── Dockerfile                      # ⭐ Docker образ для приложения
│   └── .dockerignore                   # ⭐ Исключения при сборке
│
├── 🔄 CI/CD PIPELINES
│   └── .github/
│       └── workflows/
│           ├── deploy.yml              # Workflow с GitHub Container Registry
│           └── deploy-simple.yml       # ⭐ Упрощённый workflow (РЕКОМЕНДУЕТСЯ)
│
├── ☸️  KUBERNETES ИНФРАСТРУКТУРА
│   └── k8s/
│       ├── deployment.yaml             # ⭐ K8s manifests (Deployment, Service, Ingress, PVC)
│       ├── setup.sh                    # Полная установка на microk8s
│       └── quick-setup.sh              # ⭐ Быстрая автоматическая установка
│
└── 📚 ДОКУМЕНТАЦИЯ
    ├── SUMMARY.md                      # ⭐ НАЧНИТЕ ОТСЮДА - Итоговое резюме
    ├── QUICKSTART.md                   # 5-минутный быстрый старт
    ├── DEPLOYMENT.md                   # Полная документация развертывания
    ├── GITHUB_SECRETS.md               # Как настроить GitHub Secrets
    ├── README_CICD.md                  # Обзор CI/CD инфраструктуры
    ├── COMMANDS.sh                     # Сборник всех полезных команд
    └── PROJECT_STRUCTURE.md            # Этот файл
```

---

## 🎯 Файлы, которые вам нужно использовать первыми

### 1️⃣ Прочитайте

```
SUMMARY.md  ←  Начните отсюда!
```

### 2️⃣ На microk8s сервере запустите

```bash
chmod +x k8s/quick-setup.sh
./k8s/quick-setup.sh
```

### 3️⃣ На GitHub добавьте Secrets

Используя информацию из:

```
GITHUB_SECRETS.md  ←  Пошаговая инструкция
```

### 4️⃣ Делайте push и смотрите результат

```bash
git push origin main
```

---

## 📊 Назначение каждого файла

### 🐳 Docker файлы

| Файл            | Назначение                                                       |
| --------------- | ---------------------------------------------------------------- |
| `Dockerfile`    | Собирает Docker образ с Python 3.11, зависимостями и приложением |
| `.dockerignore` | Исключает ненужные файлы из образа (уменьшает размер)            |

**Использование:** Автоматически используется GitHub Actions и microk8s

---

### 🔄 CI/CD файлы

| Файл                                  | Назначение                                         | Когда использовать                        |
| ------------------------------------- | -------------------------------------------------- | ----------------------------------------- |
| `.github/workflows/deploy.yml`        | Workflow с публикацией в GitHub Container Registry | Если хотите публичный registry            |
| `.github/workflows/deploy-simple.yml` | Workflow с локальной сборкой на microk8s           | ⭐ Для локального сервера (рекомендуется) |

**Автоматическое срабатывание:** При push в ветку `main` или `develop`

---

### ☸️ Kubernetes файлы

| Файл                  | Назначение                                                              |
| --------------------- | ----------------------------------------------------------------------- |
| `k8s/deployment.yaml` | Manifests для Kubernetes (Deployment, Service, Ingress, PVC, ConfigMap) |
| `k8s/setup.sh`        | Полная установка с GitHub Container Registry authentication             |
| `k8s/quick-setup.sh`  | ⭐ Быстрая автоматическая установка всех необходимых компонентов        |

**На какой машине:** На вашем microk8s сервере

---

### 📚 Документация

| Файл                   | Что содержит                          | Для кого                  |
| ---------------------- | ------------------------------------- | ------------------------- |
| `SUMMARY.md`           | Итоговое резюме и быстрый старт       | Все                       |
| `QUICKSTART.md`        | Шпаргалка с основными командами       | Те, кто спешит            |
| `DEPLOYMENT.md`        | Полная документация и troubleshooting | Те, кто хочет понять      |
| `GITHUB_SECRETS.md`    | Пошаговая настройка GitHub Secrets    | Для настройки GitHub      |
| `README_CICD.md`       | Архитектура и обзор системы           | Для понимания компонентов |
| `COMMANDS.sh`          | 100+ полезных команд                  | Справочник при работе     |
| `PROJECT_STRUCTURE.md` | Этот файл - структура проекта         | Для ориентации            |

---

## 🔄 Как это работает (короче)

```
1. Вы пушите код в GitHub
   ↓
2. GitHub Actions автоматически:
   - Собирает Docker образ
   - SSH подключается к вашему microk8s серверу
   - Запускает скрипт развертывания на сервере
   ↓
3. На microk8s сервере:
   - Клонируется репо
   - Собирается Docker образ локально
   - Применяются K8s manifests
   - Обновляется deployment с новым образом
   ↓
4. Kubernetes:
   - Скачивает новый образ
   - Запускает новый pod
   - Проверяет health checks
   - Удаляет старый pod
   ↓
5. ✅ Ваше приложение обновлено и работает!
```

---

## 🛠️ Что нужно сделать

### Обязательно:

1. [ ] Прочитать [`SUMMARY.md`](SUMMARY.md)
2. [ ] Запустить `./k8s/quick-setup.sh` на microk8s сервере
3. [ ] Добавить Secrets в GitHub (используя [`GITHUB_SECRETS.md`](GITHUB_SECRETS.md))
4. [ ] Сделать `git push origin main`

### Рекомендуется:

5. [ ] Прочитать [`QUICKSTART.md`](QUICKSTART.md)
6. [ ] Сохранить [`COMMANDS.sh`](COMMANDS.sh) в закладки (туда всё)
7. [ ] Прочитать [`DEPLOYMENT.md`](DEPLOYMENT.md) для полного понимания

### Опционально:

8. [ ] Прочитать [`README_CICD.md`](README_CICD.md) для понимания архитектуры
9. [ ] Настроить дополнительные компоненты (Ingress, SSL, мониторинг)

---

## 📊 Размеры файлов

```
Docker образ:        ~500-800 MB (зависит от кэша)
Python зависимости:  ~200 MB
Приложение:          ~100 KB
PersistentVolume:    5 GB (настраивается)
```

---

## ⚙️ Требования

**На microk8s сервере:**

- microk8s установлен
- Docker установлен
- Git установлен
- SSH доступ (для GitHub Actions)
- Минимум 2 GB RAM свободно
- Минимум 5 GB дискового пространства

**На вашей локальной машине:**

- Git
- Доступ к GitHub (для push)

---

## 🔐 Файлы с конфиденциальной информацией

⚠️ **Никогда не коммитьте:**

- SSH приватные ключи
- Database credentials
- API tokens
- Файлы в `/app/data/` (где БД)

✅ **Используйте вместо этого:**

- GitHub Secrets (для credentials)
- Environment variables (для конфигурации)
- ConfigMap в K8s (для переменных приложения)

---

## 📝 Файлы, которые можно редактировать

### Для изменения конфигурации приложения:

```bash
# Переменные окружения (в k8s/deployment.yaml, ConfigMap)
microk8s kubectl edit configmap itemstock-config -n itemstock

# Ресурсы (RAM, CPU)
# Отредактируйте resources в k8s/deployment.yaml:
# resources:
#   requests:
#     memory: "256Mi"  ← измените
#     cpu: "250m"      ← измените

# Количество реплик (масштабирование)
# Отредактируйте replicas в k8s/deployment.yaml:
# replicas: 1  ← измените на 3 для load balancing
```

---

## 🚀 Типичный workflow

```bash
# 1. На локальной машине разработка
vim app.py
# Сделали изменения...

# 2. Коммит и push
git add .
git commit -m "Feature: добавлена новая функция"
git push origin main

# 3. Автоматически происходит:
# GitHub Actions запускается
# Сборка образа
# SSH на microk8s сервер
# Развертывание

# 4. Проверить статус (на microk8s сервере)
microk8s kubectl get pods -n itemstock

# 5. Смотреть логи
microk8s kubectl logs -n itemstock -l app=itemstock -f

# 6. Если что-то не так, откатить
microk8s kubectl rollout undo deployment/itemstock-app -n itemstock
```

---

## 💡 Полезные советы

1. **Используйте `deploy-simple.yml`** - он безопаснее и проще для локальных серверов
2. **Регулярно проверяйте логи** - помогает выловить проблемы рано
3. **Сохраните `COMMANDS.sh`** - туда собраны все полезные команды
4. **Изучите `k8s/deployment.yaml`** - там вся конфигурация K8s
5. **Используйте SSH ключи** - безопаснее чем passwords

---

## ❓ Часто задаваемые вопросы

**Q: Где хранятся данные?**
A: В PersistentVolume по пути `/var/snap/microk8s/common/default-storage/`

**Q: Как откатить обновление?**
A: `microk8s kubectl rollout undo deployment/itemstock-app -n itemstock`

**Q: Как посмотреть логи?**
A: `microk8s kubectl logs -n itemstock -l app=itemstock -f`

**Q: Что если что-то сломалось?**
A: Смотрите [`DEPLOYMENT.md`](DEPLOYMENT.md) раздел Troubleshooting

---

## 📞 Где найти ответы

| Вопрос          | Смотрите                                 |
| --------------- | ---------------------------------------- |
| Как начать?     | [`SUMMARY.md`](SUMMARY.md)               |
| Быстрый старт?  | [`QUICKSTART.md`](QUICKSTART.md)         |
| GitHub Secrets? | [`GITHUB_SECRETS.md`](GITHUB_SECRETS.md) |
| Команды K8s?    | [`COMMANDS.sh`](COMMANDS.sh)             |
| Проблемы?       | [`DEPLOYMENT.md`](DEPLOYMENT.md)         |
| Архитектура?    | [`README_CICD.md`](README_CICD.md)       |

---

## ✅ Завершено!

Вся инфраструктура CI/CD для itemstock_mvp готова к использованию.

**Начните с:** [`SUMMARY.md`](SUMMARY.md) 👈

---

**Создано:** 2026-04-13  
**Версия:** 1.0  
**Статус:** ✅ Production-ready  
**Поддержка:** Полная документация включена

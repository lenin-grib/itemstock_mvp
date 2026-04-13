# 🔧 ИСПРАВЛЕНИЯ И ВАЖНЫЕ ЗАМЕЧАНИЯ

## ⚠️ Важно перед применением

При применении `k8s/deployment.yaml` на microk8s обратите внимание на следующее:

### 1. StorageClass

**Проблема:** microk8s уже имеет встроенный StorageClass `microk8s-hostpath`

**Решение:** Используйте встроенный, НЕ создавайте новый

- Файл `k8s/deployment.yaml` уже использует существующий StorageClass
- Если при первом применении возникнет ошибка о StorageClass, просто примените manifests ещё раз

**Команда для применения:**

```bash
microk8s kubectl apply -f k8s/deployment.yaml
```

### 2. Docker образ

**Важно:** Образ в deployment.yaml по умолчанию `itemstock:latest` (локальный)

Это означает, что:

- Образ должен быть собран на сервере ИЛИ
- GitHub Actions собирает и отправляет образ

**Для локальной сборки используйте:**

```bash
docker build -t itemstock:latest .
```

**Для использования с GitHub Actions:**
Отредактируйте `image:` в `k8s/deployment.yaml` на:

```yaml
image: ghcr.io/lenin-grib/itemstock_mvp:main-<commit_sha>
```

### 3. Health checks

**Важно:** Приложение должно отвечать на `/_stcore/health`

Это встроенный Streamlit endpoint. Если возникают проблемы:

```bash
# Проверьте вручную
curl http://localhost:8501/_stcore/health
```

---

## ✅ Правильный порядок действий

### Вариант 1: Локальная разработка и сборка на сервере

```bash
# 1. На microk8s сервере - клонируйте репо
git clone https://github.com/lenin-grib/itemstock_mvp.git
cd itemstock_mvp

# 2. Запустите быструю установку
chmod +x k8s/quick-setup.sh
./k8s/quick-setup.sh

# 3. Соберите Docker образ
docker build -t itemstock:latest .

# 4. Примените K8s manifests
microk8s kubectl apply -f k8s/deployment.yaml

# 5. Проверьте статус
microk8s kubectl get pods -n itemstock
```

### Вариант 2: Автоматическое развертывание через GitHub Actions

```bash
# На microk8s сервере выполните шаги 1-2 выше
git clone https://github.com/lenin-grib/itemstock_mvp.git
cd itemstock_mvp
chmod +x k8s/quick-setup.sh
./k8s/quick-setup.sh

# На GitHub добавьте Secrets (используя информацию из quick-setup.sh)

# На локальной машине просто пушьте код
git push origin main

# GitHub Actions автоматически:
# - Собирает образ
# - Отправляет на сервер
# - Развертывает на K8s
```

---

## 🐛 Troubleshooting

### Ошибка: "StorageClass microk8s-hostpath not found"

```bash
# Решение 1: Проверьте, что storage addon включен
microk8s enable storage

# Решение 2: Используйте встроенный
microk8s kubectl get storageclass
# Должен показать: microk8s-hostpath (default)

# Решение 3: Если все ещё не работает
microk8s kubectl apply -f k8s/deployment.yaml
# Попробуйте ещё раз
```

### Ошибка: "ImagePullBackOff" или "ErrImagePull"

```bash
# Причина 1: Образ не существует локально
docker build -t itemstock:latest .

# Причина 2: Неправильный тег образа
microk8s kubectl describe pod <pod-name> -n itemstock
# Проверьте какой образ ищет

# Причина 3: Используете GHCR
# Тогда нужно добавить imagePullSecret в deployment.yaml
```

### Pod не запускается, но нет ошибок

```bash
# Проверьте логи
microk8s kubectl logs <pod-name> -n itemstock

# Проверьте события
microk8s kubectl describe pod <pod-name> -n itemstock

# Проверьте health check
microk8s kubectl exec <pod-name> -n itemstock -- curl localhost:8501/_stcore/health
```

---

## 📝 Изменения, которые нужно сделать

### Если используете GitHub Container Registry (GHCR)

В `k8s/deployment.yaml` измените:

```yaml
# Было:
image: itemstock:latest
imagePullPolicy: IfNotPresent

# Нужно:
image: ghcr.io/lenin-grib/itemstock_mvp:main-<commit_sha>
imagePullPolicy: Always

# И добавьте в конец spec.template.spec:
imagePullSecrets:
- name: ghcr-secret
```

### Если меняете количество реплик

В `k8s/deployment.yaml`:

```yaml
spec:
  replicas: 1 # Измените на 3 для балансировки нагрузки
```

### Если меняете ресурсы

В `k8s/deployment.yaml`:

```yaml
resources:
  requests:
    memory: "256Mi" # Измените если нужно больше
    cpu: "250m" # Измените если нужно больше
  limits:
    memory: "512Mi"
    cpu: "500m"
```

---

## 🔐 GitHub Actions и SSH

### Если GitHub Actions не может подключиться к серверу

1. **Проверьте SSH ключ:**

```bash
# На сервере
cat ~/.ssh/authorized_keys | grep itemstock
```

2. **Проверьте GitHub Secrets:**
   - GitHub → Settings → Secrets and variables → Actions
   - Убедитесь, что MICROK8S_KEY правильно закодирован

3. **Проверьте вручную:**

```bash
# На локальной машине (если у вас есть ключ)
ssh -i ~/.ssh/itemstock_deploy user@server "microk8s kubectl get pods -n itemstock"
```

---

## 📊 Логирование и отладка

### Смотреть логи GitHub Actions

```
GitHub → Actions → deploy-simple.yml → Run
```

### Смотреть логи K8s

```bash
# Все логи в namespace
microk8s kubectl logs -n itemstock -l app=itemstock -f

# Логи конкретного pod
microk8s kubectl logs <pod-name> -n itemstock -f

# Логи при ошибке (предыдущего pod)
microk8s kubectl logs <pod-name> -n itemstock --previous
```

---

## ✅ Чек-лист перед первым развертыванием

- [ ] microk8s установлен и работает
- [ ] Docker установлен и работает
- [ ] Git установлен и настроен
- [ ] SSH ключ сгенерирован на сервере
- [ ] SSH ключ добавлен в GitHub Secrets
- [ ] Все 3 Secrets добавлены в GitHub (MICROK8S_HOST, MICROK8S_USER, MICROK8S_KEY)
- [ ] `k8s/deployment.yaml` подходит для вашей конфигурации
- [ ] Docker образ можно собрать локально: `docker build -t itemstock:latest .`
- [ ] microk8s kubectl apply работает без ошибок
- [ ] Pod успешно запустился

---

## 🎯 Рекомендуемые команды для отладки

```bash
# 1. Проверить статус microk8s
microk8s status

# 2. Проверить addons
microk8s status --addon

# 3. Проверить namespace
microk8s kubectl get namespace itemstock

# 4. Проверить pods
microk8s kubectl get pods -n itemstock -o wide

# 5. Проверить services
microk8s kubectl get svc -n itemstock

# 6. Проверить PVC
microk8s kubectl get pvc -n itemstock

# 7. Проверить events
microk8s kubectl get events -n itemstock

# 8. Описание pod
microk8s kubectl describe pod <pod-name> -n itemstock

# 9. Логи pod
microk8s kubectl logs <pod-name> -n itemstock

# 10. Получить IP сервиса
microk8s kubectl get svc itemstock-service -n itemstock -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

---

## 🚀 После успешного развертывания

1. **Проверьте доступность:**

```bash
curl http://<SERVICE_IP>:80
# или
http://localhost:8501 (если на локальной машине)
```

2. **Проверьте данные:**

```bash
microk8s kubectl exec <pod-name> -n itemstock -- ls -la /app/data
```

3. **Проверьте логи приложения:**

```bash
microk8s kubectl logs <pod-name> -n itemstock -f
```

---

## 📚 Дополнительные ресурсы

- Логирование ошибок: см. [`DEPLOYMENT.md`](DEPLOYMENT.md) раздел Troubleshooting
- Все команды: [`COMMANDS.sh`](COMMANDS.sh)
- Полная документация: [`DEPLOYMENT.md`](DEPLOYMENT.md)

---

**Версия:** 1.1  
**Обновлено:** 2026-04-13  
**Статус:** ✅ Готово к использованию

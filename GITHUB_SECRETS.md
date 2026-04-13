# GitHub Secrets Configuration для itemstock_mvp

Этот файл объясняет, как настроить GitHub Secrets для автоматического развертывания на microk8s.

## 📍 Где находятся GitHub Secrets?

1. Откройте ваш репозиторий на GitHub
2. Settings (Настройки) → Secrets and variables → Actions
3. Нажмите "New repository secret"

## 🔐 Требуемые Secrets

### Для workflow `deploy-simple.yml` (рекомендуется для локального microk8s)

#### 1. MICROK8S_HOST

**Что это:** IP адрес или hostname вашего microk8s сервера

**Как получить:**

```bash
# На microk8s сервере
hostname -I
# или
echo $(hostname)
```

**Пример значения:**

```
192.168.1.100
или
microk8s.example.com
```

---

#### 2. MICROK8S_USER

**Что это:** SSH пользователь для подключения к серверу

**Как получить:**

```bash
# На microk8s сервере
whoami
```

**Пример значения:**

```
ubuntu
или
root
или
deploy
```

---

#### 3. MICROK8S_KEY

**Что это:** Private SSH ключ (закодирован в base64) для подключения к серверу

**Как получить:**

Вариант 1 - Использовать существующий ключ:

```bash
# На вашей локальной машине
cat ~/.ssh/id_rsa | base64 -w 0
```

Вариант 2 - Сгенерировать новый ключ на microk8s сервере:

```bash
# На microk8s сервере
ssh-keygen -t ed25519 -f ~/.ssh/itemstock_deploy -N ""

# Добавить в authorized_keys
cat ~/.ssh/itemstock_deploy.pub >> ~/.ssh/authorized_keys

# Получить private ключ в base64
cat ~/.ssh/itemstock_deploy | base64 -w 0
```

**Важно:** Не теряйте `-w 0` флаг, он нужен для однострочного формата!

**Пример вывода:**

```
LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0KYjNCNWNtRjBZMmhoYm01bFlXTmxDZ0FBQUFJUkVFQktSZ0JoQVRGck5...
(очень длинная строка)
...ZWQZEVDVFJZVA0tLS0tRU5EIE9QRU5TU0ggUFJJVkFURSBLRVktLS0tLQo=
```

---

## 🔧 Для workflow `deploy.yml` (с GitHub Container Registry)

Если используете `deploy.yml` с GHCR, добавьте дополнительный secret:

#### 4. MICROK8S_KUBECONFIG

**Что это:** kubeconfig файл (закодирован в base64) для доступа к кластеру

**Как получить:**

```bash
# На microk8s сервере
cat /var/snap/microk8s/current/credentials/client.config | base64 -w 0

# Или, если используете ~/.kube/config
cat ~/.kube/config | base64 -w 0
```

**Где использовать:** Только в `.github/workflows/deploy.yml`

---

## ✅ Пошаговая инструкция

### Шаг 1: Подготовка SSH ключа

```bash
# На microk8s сервере (если не используете существующий ключ)
ssh-keygen -t ed25519 -f ~/.ssh/itemstock_deploy -N ""

# Добавить публичный ключ в authorized_keys
cat ~/.ssh/itemstock_deploy.pub >> ~/.ssh/authorized_keys

# Проверить
cat ~/.ssh/authorized_keys | grep itemstock_deploy
```

### Шаг 2: Получение значений для Secrets

```bash
# 1. MICROK8S_HOST
hostname -I

# 2. MICROK8S_USER
whoami

# 3. MICROK8S_KEY (базовая кодировка)
cat ~/.ssh/itemstock_deploy | base64 -w 0

# Скопируйте весь вывод (очень длинная строка)
```

### Шаг 3: Добавление Secrets в GitHub

1. Откройте репозиторий на GitHub
2. Settings → Secrets and variables → Actions
3. Нажмите "New repository secret"
4. Добавьте каждый secret:

| Name          | Value                          |
| ------------- | ------------------------------ |
| MICROK8S_HOST | `<IP_адрес_или_hostname>`      |
| MICROK8S_USER | `<ssh_пользователь>`           |
| MICROK8S_KEY  | `<base64_закодированный_ключ>` |

### Шаг 4: Проверка подключения

На microk8s сервере проверьте, что SSH работает:

```bash
# На вашей локальной машине
ssh -i ~/.ssh/itemstock_deploy <MICROK8S_USER>@<MICROK8S_HOST> "microk8s kubectl get pods -n itemstock"
```

---

## 🧪 Тестирование

### Проверить подключение вручную:

```bash
# На вашей локальной машине (если у вас есть ключ)
ssh -i ~/.ssh/itemstock_deploy user@192.168.1.100 "date"

# Должно вывести текущую дату на сервере
```

### Запустить GitHub Actions вручную:

```bash
# После добавления secrets, сделайте push
git push origin main

# Или вручную в GitHub Actions → deploy-simple.yml → Run workflow
```

### Просмотреть логи GitHub Actions:

1. Откройте репозиторий на GitHub
2. Actions → deploy-simple.yml
3. Выберите последний run
4. Просмотрите логи для каждого шага

---

## 🔍 Отладка

### Если подключение не работает:

#### Проблема: "Permission denied (publickey)"

```bash
# На microk8s сервере - проверьте authorized_keys
cat ~/.ssh/authorized_keys

# Проверьте права доступа
ls -la ~/.ssh/
# Должно быть: drwx------ (700) для .ssh

chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
```

#### Проблема: "base64: command not found" на macOS

```bash
# macOS использует другую команду
cat ~/.ssh/itemstock_deploy | base64
```

#### Проблема: Secret не работает в workflow

1. Проверьте, что Secret добавлен в правильный репозиторий
2. Проверьте точное имя Secret (case-sensitive)
3. Сделайте новый push для срабатывания workflow

---

## 📋 Чек-лист

- [ ] Создан SSH ключ (`~/.ssh/itemstock_deploy`)
- [ ] Публичный ключ добавлен в `authorized_keys`
- [ ] Получено значение для `MICROK8S_HOST` (IP или hostname)
- [ ] Получено значение для `MICROK8S_USER` (например: ubuntu)
- [ ] Получено значение для `MICROK8S_KEY` (base64 закодированный приватный ключ)
- [ ] Все 3 Secrets добавлены в GitHub Settings
- [ ] SSH подключение работает вручную
- [ ] Сделан push в GitHub для запуска workflow

---

## 🔒 Безопасность

**Никогда не делайте:**

- ❌ Не коммитьте приватные SSH ключи в репозиторий
- ❌ Не вставляйте Secrets в код
- ❌ Не делитесь значениями Secrets с другими
- ❌ Не используйте root ключи в production

**Всегда делайте:**

- ✅ Используйте отдельный ключ для каждого сервиса
- ✅ Ограничивайте права SSH пользователя
- ✅ Регулярно ротируйте ключи
- ✅ Используйте GitHub Secrets для конфиденциальных данных

---

## 📚 Дополнительные ресурсы

- [GitHub Secrets Documentation](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [SSH Key Generation Guide](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent)
- [microk8s Documentation](https://microk8s.io/)

---

## ❓ Часто задаваемые вопросы

**Q: Почему мне нужно использовать base64?**
A: GitHub Secrets поддерживают только текст, а приватные ключи содержат специальные символы. Base64 преобразует их в текстовый формат.

**Q: Безопасно ли хранить приватные ключи в GitHub Secrets?**
A: Да, GitHub Secrets зашифрованы и доступны только в контексте GitHub Actions.

**Q: Что если я потеряю приватный ключ?**
A: Сгенерируйте новый ключ и обновите Secret в GitHub.

**Q: Можно ли использовать password вместо ключа?**
A: Можно, но не рекомендуется. SSH ключи безопаснее и удобнее.

---

**Готово!** Теперь ваш микро8s сервер подключен к GitHub Actions и готов к автоматическому развертыванию. 🚀

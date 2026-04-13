# 🗂️ ИНДЕКС ДОКУМЕНТАЦИИ - itemstock_mvp CI/CD

**Быстрая навигация по всей документации**

---

## ⭐ НАЧНИТЕ ОТСЮДА (первое, что нужно прочитать)

### 🎯 [`SUMMARY.md`](SUMMARY.md)

- Что было создано
- Быстрый старт в 3 шага
- Архитектура системы
- Чек-лист первоначальной настройки

**Время на чтение:** 10 минут  
**Результат:** Понимание всей системы

---

## 🚀 БЫСТРЫЙ СТАРТ

### 📝 [`QUICKSTART.md`](QUICKSTART.md)

- Быстрая шпаргалка с основными командами
- Мониторинг приложения
- Troubleshooting частых проблем
- Полезные советы

**Время на чтение:** 5 минут  
**Результат:** Готовы к использованию

**Основные команды:**

```bash
# На microk8s сервере
./k8s/quick-setup.sh

# Проверить статус
microk8s kubectl get pods -n itemstock

# Смотреть логи
microk8s kubectl logs -n itemstock -l app=itemstock -f
```

---

## ⚙️ НАСТРОЙКА

### 🔐 [`GITHUB_SECRETS.md`](GITHUB_SECRETS.md)

- Пошаговая настройка GitHub Secrets
- Как получить каждый параметр
- Примеры значений
- Отладка проблем с подключением

**Время на чтение:** 15 минут  
**Результат:** GitHub готов к автоматическому развертыванию

**Требуемые Secrets:**

```
MICROK8S_HOST = <IP вашего сервера>
MICROK8S_USER = <SSH пользователь>
MICROK8S_KEY = <base64 SSH ключ>
```

---

## 📚 ПОЛНАЯ ДОКУМЕНТАЦИЯ

### 📖 [`DEPLOYMENT.md`](DEPLOYMENT.md)

- Подробное описание всех компонентов
- Процесс работы по шагам
- Мониторинг и управление
- Команды для отладки
- Решения для частых проблем

**Время на чтение:** 30 минут  
**Результат:** Полное понимание всей системы

**Содержит:**

- Компоненты (Docker, GitHub Actions, K8s)
- Инструкции по настройке
- Команды мониторинга
- Troubleshooting guide

---

### 🏗️ [`README_CICD.md`](README_CICD.md)

- Архитектура инфраструктуры
- Обзор компонентов
- Файлы проекта
- FAQ
- Следующие шаги

**Время на чтение:** 15 минут  
**Результат:** Понимание архитектуры

---

### 📂 [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md)

- Структура всех файлов проекта
- Назначение каждого файла
- Какие файлы редактировать
- Типичный workflow
- Полезные советы

**Время на чтение:** 10 минут  
**Результат:** Знание, где что находится

---

## 🛠️ СПРАВОЧНИК КОМАНД

### 💻 [`COMMANDS.sh`](COMMANDS.sh)

**100+ команд разбито по категориям:**

1. **Установка и настройка**

   ```bash
   ./k8s/quick-setup.sh
   microk8s enable dns storage ingress
   ```

2. **Развертывание**

   ```bash
   git push origin main
   microk8s kubectl set image deployment/itemstock-app ...
   ```

3. **Мониторинг**

   ```bash
   microk8s kubectl get pods -n itemstock
   microk8s kubectl logs -n itemstock -l app=itemstock -f
   ```

4. **Отладка**

   ```bash
   microk8s kubectl exec -it <pod> -n itemstock -- bash
   microk8s kubectl describe pod <pod> -n itemstock
   ```

5. **Управление**

   ```bash
   microk8s kubectl scale deployment itemstock-app --replicas=3
   microk8s kubectl rollout undo deployment/itemstock-app
   ```

6. **Резервная копия**
   ```bash
   microk8s kubectl cp itemstock/<pod>:/app/data ./backup
   ```

**Время на чтение:** 20 минут  
**Результат:** Справочник со всеми нужными командами

---

## 📊 МАТРИЦА ПОМОЩИ

| Что вам нужно            | Смотрите файл                                  | Раздел               |
| ------------------------ | ---------------------------------------------- | -------------------- |
| Быстрый старт            | [`SUMMARY.md`](SUMMARY.md)                     | Быстрый старт        |
| Понять, как это работает | [`README_CICD.md`](README_CICD.md)             | Архитектура          |
| Настроить GitHub         | [`GITHUB_SECRETS.md`](GITHUB_SECRETS.md)       | Пошаговая инструкция |
| Найти команду            | [`COMMANDS.sh`](COMMANDS.sh)                   | Категории            |
| Решить проблему          | [`DEPLOYMENT.md`](DEPLOYMENT.md)               | Troubleshooting      |
| Узнать структуру         | [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md) | Файлы проекта        |

---

## 🎯 ПО СЦЕНАРИЯМ

### Я только начинаю

1. Прочитайте [`SUMMARY.md`](SUMMARY.md)
2. Следуйте "Быстрому старту" в 3 шага
3. Используйте [`QUICKSTART.md`](QUICKSTART.md) для справки

**Время:** ~30 минут до первого развертывания

---

### Я хочу понять, как это работает

1. Прочитайте [`README_CICD.md`](README_CICD.md)
2. Посмотрите архитектуру в [`SUMMARY.md`](SUMMARY.md)
3. Изучите [`DEPLOYMENT.md`](DEPLOYMENT.md)

**Время:** ~1 час для полного понимания

---

### У меня есть проблема

1. Проверьте логи: `microk8s kubectl logs -n itemstock -l app=itemstock`
2. Смотрите [`DEPLOYMENT.md`](DEPLOYMENT.md) → Troubleshooting
3. Проверьте [`COMMANDS.sh`](COMMANDS.sh) для отладки

**Время:** ~15 минут для решения

---

### Я хочу изменить что-то

1. Прочитайте [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md)
2. Найдите нужный файл
3. Используйте [`COMMANDS.sh`](COMMANDS.sh) для применения изменений

**Время:** Зависит от сложности

---

## 📋 ХРОНОЛОГИЧЕСКИЙ ПОРЯДОК

### День 1 - Первоначальная настройка

1. Прочитайте [`SUMMARY.md`](SUMMARY.md) (10 мин)
2. Запустите `./k8s/quick-setup.sh` на сервере (5 мин)
3. Следуйте [`GITHUB_SECRETS.md`](GITHUB_SECRETS.md) (15 мин)
4. Сделайте `git push origin main` (1 мин)
5. Проверьте статус (5 мин)

**Итого:** ~40 минут

### День 2+ - Ежедневное использование

- Используйте [`QUICKSTART.md`](QUICKSTART.md) как шпаргалку
- Используйте [`COMMANDS.sh`](COMMANDS.sh) для поиска команд
- Смотрите логи для мониторинга

---

## 🔍 ПОИСК ПО КЛЮЧЕВЫМ СЛОВАМ

| Ищете                | Файл                                                                         | Строка поиска         |
| -------------------- | ---------------------------------------------------------------------------- | --------------------- |
| Docker образ         | [`Dockerfile`](Dockerfile)                                                   | Dockerfile            |
| GitHub Actions       | [`.github/workflows/deploy-simple.yml`](.github/workflows/deploy-simple.yml) | workflow              |
| K8s deployment       | [`k8s/deployment.yaml`](k8s/deployment.yaml)                                 | apiVersion            |
| Быструю команду      | [`COMMANDS.sh`](COMMANDS.sh)                                                 | grep "что ищу"        |
| Переменные окружения | [`k8s/deployment.yaml`](k8s/deployment.yaml)                                 | ConfigMap             |
| Health check         | [`k8s/deployment.yaml`](k8s/deployment.yaml)                                 | livenessProbe         |
| SSH ключ             | [`GITHUB_SECRETS.md`](GITHUB_SECRETS.md)                                     | MICROK8S_KEY          |
| PersistentVolume     | [`k8s/deployment.yaml`](k8s/deployment.yaml)                                 | PersistentVolumeClaim |

---

## 📞 КОНТАКТ И ПОМОЩЬ

### Если что-то не понятно

1. Проверьте матрицу помощи выше
2. Поищите в [`COMMANDS.sh`](COMMANDS.sh)
3. Прочитайте соответствующий раздел в [`DEPLOYMENT.md`](DEPLOYMENT.md)

### Если что-то сломалось

1. Посмотрите логи (см. [`QUICKSTART.md`](QUICKSTART.md))
2. Смотрите Troubleshooting в [`DEPLOYMENT.md`](DEPLOYMENT.md)
3. Проверьте GitHub Actions логи

### Если нужна справка

- Команды: [`COMMANDS.sh`](COMMANDS.sh)
- Процесс: [`DEPLOYMENT.md`](DEPLOYMENT.md)
- Архитектура: [`README_CICD.md`](README_CICD.md)

---

## ✅ ЧЕК-ЛИСТ ЗАВЕРШЕНИЯ

- [ ] Прочитал [`SUMMARY.md`](SUMMARY.md)
- [ ] Запустил `./k8s/quick-setup.sh`
- [ ] Добавил Secrets в GitHub (используя [`GITHUB_SECRETS.md`](GITHUB_SECRETS.md))
- [ ] Сделал `git push origin main`
- [ ] Проверил статус с помощью [`QUICKSTART.md`](QUICKSTART.md)
- [ ] Сохранил [`COMMANDS.sh`](COMMANDS.sh) в закладки
- [ ] Прочитал [`DEPLOYMENT.md`](DEPLOYMENT.md) (опционально)

---

## 🎓 ДОПОЛНИТЕЛЬНОЕ ОБУЧЕНИЕ

- **Kubernetes:** https://kubernetes.io/docs/
- **microk8s:** https://microk8s.io/docs
- **GitHub Actions:** https://docs.github.com/en/actions
- **Docker:** https://docs.docker.com/
- **Streamlit:** https://docs.streamlit.io/

---

## 📊 СТАТИСТИКА ДОКУМЕНТАЦИИ

| Файл                 | Строк     | Время чтения |
| -------------------- | --------- | ------------ |
| SUMMARY.md           | 300       | 10 мин       |
| QUICKSTART.md        | 150       | 5 мин        |
| DEPLOYMENT.md        | 500       | 30 мин       |
| GITHUB_SECRETS.md    | 400       | 15 мин       |
| README_CICD.md       | 350       | 15 мин       |
| PROJECT_STRUCTURE.md | 350       | 10 мин       |
| COMMANDS.sh          | 500+      | 20 мин       |
| **ИТОГО**            | **~2500** | **~100 мин** |

---

## 🚀 СОКРАЩЕННЫЙ ПУТЬ (20 минут)

Если вы в спешке:

```bash
# Шаг 1: Прочитайте итоговое резюме
cat SUMMARY.md

# Шаг 2: На microk8s сервере
chmod +x k8s/quick-setup.sh
./k8s/quick-setup.sh

# Шаг 3: Добавьте Secrets в GitHub Settings
# (Смотрите GITHUB_SECRETS.md для значений)

# Шаг 4: Push код
git push origin main

# Готово! ✅
```

---

## 💡 PRO СОВЕТЫ

1. **Сохраните этот индекс** - он упростит навигацию
2. **Используйте `grep`** для поиска в командах:
   ```bash
   grep "что ищу" COMMANDS.sh
   ```
3. **Сохраните `QUICKSTART.md`** - он часто нужен
4. **Проверяйте логи часто** - они показывают все проблемы
5. **Делайте резервные копии** - используйте команды из [`COMMANDS.sh`](COMMANDS.sh)

---

## 🎉 ГОТОВО!

Вся инфраструктура CI/CD настроена и полностью задокументирована.

**Начните:** Прочитайте [`SUMMARY.md`](SUMMARY.md) 👈

---

**Версия:** 1.0  
**Создано:** 2026-04-13  
**Статус:** ✅ Complete

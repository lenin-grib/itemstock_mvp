#!/bin/bash

# 📋 Сборник всех команд для управления itemstock_mvp на microk8s
# Используйте этот файл как справочник

echo "itemstock_mvp - Сборник команд"
echo "================================"
echo ""
echo "Выберите категорию:"
echo "1. Установка и настройка"
echo "2. Развертывание"
echo "3. Мониторинг"
echo "4. Отладка"
echo "5. Управление"
echo "6. Резервная копия"
echo ""

# ============================================
# 1. УСТАНОВКА И НАСТРОЙКА
# ============================================

cat << 'EOF'
╔════════════════════════════════════════════════════════════╗
║ 1️⃣  УСТАНОВКА И НАСТРОЙКА (на microk8s сервере)
╚════════════════════════════════════════════════════════════╝

# Быстрая установка (рекомендуется)
./k8s/quick-setup.sh

# Полная установка с GitHub Container Registry
./k8s/setup.sh YOUR_GITHUB_USERNAME YOUR_GITHUB_TOKEN

# Включить необходимые addons
microk8s enable dns storage ingress

# Создать namespace
microk8s kubectl create namespace itemstock

# Применить K8s manifests
microk8s kubectl apply -f k8s/deployment.yaml

# Получить SSH ключ для GitHub (base64)
cat ~/.ssh/itemstock_deploy | base64 -w 0

# Получить kubeconfig (base64) - для deploy.yml с GHCR
cat /var/snap/microk8s/current/credentials/client.config | base64

EOF

# ============================================
# 2. РАЗВЕРТЫВАНИЕ
# ============================================

cat << 'EOF'
╔════════════════════════════════════════════════════════════╗
║ 2️⃣  РАЗВЕРТЫВАНИЕ
╚════════════════════════════════════════════════════════════╝

# Автоматическое (при push в GitHub)
git push origin main

# Ручное обновление image
microk8s kubectl set image deployment/itemstock-app \
  itemstock=itemstock:v1.0 -n itemstock

# Принудительный перезапуск deployment
microk8s kubectl rollout restart deployment/itemstock-app -n itemstock

# Просмотр истории развертываний
microk8s kubectl rollout history deployment/itemstock-app -n itemstock

# Откат к предыдущей версии
microk8s kubectl rollout undo deployment/itemstock-app -n itemstock

# Откат к конкретной версии
microk8s kubectl rollout undo deployment/itemstock-app --to-revision=2 -n itemstock

# Пауза развертывания (для отладки)
microk8s kubectl rollout pause deployment/itemstock-app -n itemstock

# Возобновление развертывания
microk8s kubectl rollout resume deployment/itemstock-app -n itemstock

EOF

# ============================================
# 3. МОНИТОРИНГ
# ============================================

cat << 'EOF'
╔════════════════════════════════════════════════════════════╗
║ 3️⃣  МОНИТОРИНГ
╚════════════════════════════════════════════════════════════╝

# Статус pods
microk8s kubectl get pods -n itemstock

# Статус с подробностями
microk8s kubectl get pods -n itemstock -o wide

# Все ресурсы в namespace
microk8s kubectl get all -n itemstock

# Статус deployment
microk8s kubectl get deployment -n itemstock

# Статус сервиса
microk8s kubectl get svc -n itemstock

# Информация о сервисе (включая IP)
microk8s kubectl get svc itemstock-service -n itemstock -o wide

# Статус Ingress
microk8s kubectl get ingress -n itemstock

# PersistentVolume Claims
microk8s kubectl get pvc -n itemstock

# События в namespace
microk8s kubectl get events -n itemstock

# Логи в реальном времени
microk8s kubectl logs -n itemstock -l app=itemstock -f

# Логи конкретного pod
microk8s kubectl logs <pod-name> -n itemstock

# Логи предыдущего pod (если был перезапуск)
microk8s kubectl logs <pod-name> -n itemstock --previous

# Последние 100 строк логов
microk8s kubectl logs -n itemstock -l app=itemstock --tail=100

# Логи всех containers в pod
microk8s kubectl logs <pod-name> -n itemstock --all-containers=true

# Использование ресурсов
microk8s kubectl top nodes
microk8s kubectl top pods -n itemstock

# Описание pod (подробная информация)
microk8s kubectl describe pod <pod-name> -n itemstock

# Описание deployment
microk8s kubectl describe deployment itemstock-app -n itemstock

EOF

# ============================================
# 4. ОТЛАДКА
# ============================================

cat << 'EOF'
╔════════════════════════════════════════════════════════════╗
║ 4️⃣  ОТЛАДКА
╚════════════════════════════════════════════════════════════╝

# Выполнить команду в pod
microk8s kubectl exec -it <pod-name> -n itemstock -- bash

# Выполнить python команду
microk8s kubectl exec <pod-name> -n itemstock -- python -c "print('test')"

# Посмотреть переменные окружения
microk8s kubectl exec <pod-name> -n itemstock -- env

# Просмотр файлов в pod
microk8s kubectl exec <pod-name> -n itemstock -- ls -la /app

# Port forward для локального доступа
microk8s kubectl port-forward <pod-name> 8501:8501 -n itemstock

# Port forward для сервиса
microk8s kubectl port-forward svc/itemstock-service 8501:80 -n itemstock

# Копирование файла из pod
microk8s kubectl cp itemstock/<pod-name>:/app/data/file.db ./file.db

# Копирование файла в pod
microk8s kubectl cp ./file.txt itemstock/<pod-name>:/app/data/file.txt

# Проверка health check endpoint
curl http://<SERVICE_IP>:8501/_stcore/health

# YAML deployment
microk8s kubectl get deployment itemstock-app -n itemstock -o yaml

# YAML pod
microk8s kubectl get pod <pod-name> -n itemstock -o yaml

# Просмотр образов используемых в pod
microk8s kubectl get pods -n itemstock -o jsonpath='{.items[*].spec.containers[*].image}'

EOF

# ============================================
# 5. УПРАВЛЕНИЕ
# ============================================

cat << 'EOF'
╔════════════════════════════════════════════════════════════╗
║ 5️⃣  УПРАВЛЕНИЕ
╚════════════════════════════════════════════════════════════╝

# Масштабирование (остановка)
microk8s kubectl scale deployment itemstock-app --replicas=0 -n itemstock

# Масштабирование (запуск)
microk8s kubectl scale deployment itemstock-app --replicas=1 -n itemstock

# Увеличение реплик (для балансировки нагрузки)
microk8s kubectl scale deployment itemstock-app --replicas=3 -n itemstock

# Удаление pod (автоматически пересоздастся)
microk8s kubectl delete pod <pod-name> -n itemstock

# Редактирование deployment
microk8s kubectl edit deployment itemstock-app -n itemstock

# Редактирование ConfigMap
microk8s kubectl edit configmap itemstock-config -n itemstock

# Перезаполнение ConfigMap
microk8s kubectl create configmap itemstock-config \
  --from-literal=STREAMLIT_SERVER_PORT=8501 \
  -n itemstock --dry-run=client -o yaml | microk8s kubectl replace -f -

# Просмотр ConfigMap
microk8s kubectl get configmap itemstock-config -n itemstock -o yaml

# Просмотр Secrets
microk8s kubectl get secrets -n itemstock

# Просмотр Docker образов на хосте
docker image ls | grep itemstock

# Удаление старых Docker образов
docker image prune -a

# Очистка всего namespace
microk8s kubectl delete namespace itemstock

# Пересоздание namespace с manifests
microk8s kubectl apply -f k8s/deployment.yaml

EOF

# ============================================
# 6. РЕЗЕРВНАЯ КОПИЯ И ДАННЫЕ
# ============================================

cat << 'EOF'
╔════════════════════════════════════════════════════════════╗
║ 6️⃣  РЕЗЕРВНАЯ КОПИЯ И ДАННЫЕ
╚════════════════════════════════════════════════════════════╝

# Экспортировать ConfigMap
microk8s kubectl get configmap itemstock-config -n itemstock -o yaml > backup-config.yaml

# Экспортировать весь namespace
microk8s kubectl get all -n itemstock -o yaml > backup-all.yaml

# Экспортировать только deployment
microk8s kubectl get deployment itemstock-app -n itemstock -o yaml > backup-deployment.yaml

# Путь к PersistentVolume на хосте
/var/snap/microk8s/common/default-storage/

# Скопировать данные с pod
microk8s kubectl cp itemstock/<pod-name>:/app/data ./data-backup

# Скопировать данные в pod
microk8s kubectl cp ./data-backup itemstock/<pod-name>:/app/

# Список PVC
microk8s kubectl get pvc -n itemstock

# Информация о PVC
microk8s kubectl describe pvc itemstock-data -n itemstock

# Размер PVC
microk8s kubectl get pvc -n itemstock -o jsonpath='{.items[0].spec.resources.requests.storage}'

EOF

# ============================================
# ДОПОЛНИТЕЛЬНО
# ============================================

cat << 'EOF'
╔════════════════════════════════════════════════════════════╗
║ 🔧 ДОПОЛНИТЕЛЬНО
╚════════════════════════════════════════════════════════════╝

# Справка по kubectl
microk8s kubectl --help

# Версия microk8s
microk8s version

# Статус microk8s
microk8s status

# Включенные addons
microk8s status --addon

# Перезагрузить microk8s
microk8s stop && microk8s start

# Информация о кластере
microk8s kubectl cluster-info

# Узлы кластера
microk8s kubectl get nodes

# Подробно об узле
microk8s kubectl describe node <node-name>

# DNS проверка
microk8s kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup itemstock-service.itemstock

EOF

echo ""
echo "════════════════════════════════════════════════════════"
echo "✅ Для полной документации смотрите:"
echo "   - QUICKSTART.md"
echo "   - DEPLOYMENT.md"
echo "   - README_CICD.md"
echo "════════════════════════════════════════════════════════"

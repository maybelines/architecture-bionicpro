# BionicPRO

## Задание 1. Безопасность

[Диаграмма C4](Task1/BionicPRO.drawio).

Для каждой страны предлагается отдельный контур с локальными Keycloak, BFF и базами данных. Keycloak получает учётные записи из местного LDAP по LDAPS и подключает местные IdP по OIDC или SAML. Данные пациентов и сессии остаются в своём контуре.

В этой схеме BFF обменивает код с PKCE на токены и хранит их на сервере. Клиент получает только идентификатор сессии. BFF и внешние IdP в учебном приложении не реализованы.

В существующем приложении включён Authorization Code Flow с PKCE S256 в `frontend/src/App.tsx`. Keycloak требует S256 для клиента `reports-frontend`; Implicit Flow и Direct Access Grants выключены в `keycloak/realm-export.json`.

## Задание 2. Сервис отчётов

[Описание запуска и проверки](Task2/README.md).

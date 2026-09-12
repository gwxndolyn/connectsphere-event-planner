# ConnectSphere Event Planner — Backend

Spring Boot 3 (Java 17) REST API, built with Maven. Uses Spring Web and Spring Data JPA,
backed by H2 in-memory for local development (swap the `spring.datasource` block in
`application.yml` for MySQL/Postgres when deploying).

## Prerequisites

- Java 17
- Maven (or use the included wrapper if one is added later)

## Run the app

```bash
mvn spring-boot:run
```

The app starts on `http://localhost:8080`. Health check:

```bash
curl http://localhost:8080/api/events/health
```

The H2 console is available at `http://localhost:8080/h2-console` (JDBC URL: `jdbc:h2:mem:connectsphere`).

## Run tests

```bash
mvn test
```

## Package layout

Feature-based packages under `com.connectsphere`:

- `event` — event request, review, status management
- `venue` — venue catalogue, booking, conflict detection
- `equipment` — equipment catalogue, reservation
- `registration` — attendee registration, waitlist
- `notification` — cross-cutting notification service
- `user` — auth, roles
- `common` — shared config, exceptions, DTOs

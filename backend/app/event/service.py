class EventService:
    def health(self) -> str:
        return "event service is up"


event_service = EventService()

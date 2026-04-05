"""Шаблоны проектов внедрения PASS24.

4 преднастроенных типа проектов с фазами и задачами. При создании проекта
фазы и задачи копируются из шаблона в БД. Шаблоны — read-only в MVP,
редактирование в админке не предусмотрено.

Структура:
    PROJECT_TEMPLATES[ProjectType] = TemplateDefinition
        .title: str
        .description: str
        .phases: list[TemplatePhase]
            .order, .name, .description, .duration_days, .weight
            .tasks: list[TemplateTask]
                .title, .description, .is_milestone, .estimated_hours
"""

from dataclasses import dataclass, field
from typing import Dict, List

from backend.projects.models import ProjectType


@dataclass(frozen=True)
class TemplateTask:
    title: str
    description: str = ""
    is_milestone: bool = False
    estimated_hours: int = 4


@dataclass(frozen=True)
class TemplatePhase:
    order: int
    name: str
    description: str
    duration_days: int
    weight: int = 1
    tasks: List[TemplateTask] = field(default_factory=list)


@dataclass(frozen=True)
class TemplateDefinition:
    title: str
    description: str
    phases: List[TemplatePhase]

    @property
    def total_duration_days(self) -> int:
        return sum(p.duration_days for p in self.phases)


# ---------------------------------------------------------------------------
# Шаблон 1: Стандартный ЖК (residential) — 10 фаз, ~10 недель
# ---------------------------------------------------------------------------

RESIDENTIAL_TEMPLATE = TemplateDefinition(
    title="Стандартный ЖК",
    description="Типовое внедрение PASS24 в жилом комплексе: 10 фаз от kickoff до handover, ~10 недель.",
    phases=[
        TemplatePhase(
            order=1, name="Kickoff & Planning", duration_days=5, weight=1,
            description="Запуск проекта, согласование команды, обзор объекта",
            tasks=[
                TemplateTask("Встреча с клиентом (kickoff)", is_milestone=True, estimated_hours=3),
                TemplateTask("Согласовать контакты и доступы на объект"),
                TemplateTask("Подписать NDA", estimated_hours=1),
                TemplateTask("Составить детальный план-график"),
            ],
        ),
        TemplatePhase(
            order=2, name="Procurement & Pre-Installation", duration_days=14, weight=1,
            description="Закупка оборудования, подготовка к монтажу",
            tasks=[
                TemplateTask("Составить спецификацию оборудования (BOM)", estimated_hours=8),
                TemplateTask("Закупка контроллеров и считывателей", estimated_hours=4),
                TemplateTask("Закупка кабеля и монтажных материалов", estimated_hours=2),
                TemplateTask("Подготовка инструмента и логистика на объект"),
            ],
        ),
        TemplatePhase(
            order=3, name="Hardware Installation", duration_days=21, weight=2,
            description="Монтаж оборудования на объекте: КПП, подъезды, шлагбаумы",
            tasks=[
                TemplateTask("Монтаж СКУД на главном КПП", estimated_hours=16),
                TemplateTask("Установка считывателей в подъездах", estimated_hours=24),
                TemplateTask("Прокладка СКС и подключение питания", is_milestone=True, estimated_hours=32),
                TemplateTask("Монтаж шлагбаумов на парковке", estimated_hours=16),
                TemplateTask("Фотофиксация каждой точки монтажа"),
            ],
        ),
        TemplatePhase(
            order=4, name="Software Configuration", duration_days=14, weight=1,
            description="Создание объекта в PASS24.online, настройка зон и правил",
            tasks=[
                TemplateTask("Создать объект в PASS24.online", estimated_hours=2),
                TemplateTask("Настроить pass24.control для всех точек", estimated_hours=8),
                TemplateTask("Импорт плана здания и разметка зон", estimated_hours=6),
                TemplateTask("Настройка правил доступа по ролям", estimated_hours=4),
            ],
        ),
        TemplatePhase(
            order=5, name="User Data Import", duration_days=7, weight=1,
            description="Загрузка списков жильцов, выдача доступов",
            tasks=[
                TemplateTask("Получить список жильцов от УК"),
                TemplateTask("Валидация и нормализация данных", estimated_hours=4),
                TemplateTask("Массовый импорт через CSV", is_milestone=True, estimated_hours=2),
                TemplateTask("Настройка мобильного доступа (pass24.key)"),
            ],
        ),
        TemplatePhase(
            order=6, name="Training", duration_days=7, weight=1,
            description="Обучение УК и охраны работе с системой",
            tasks=[
                TemplateTask("Тренинг администраторов УК", is_milestone=True, estimated_hours=4),
                TemplateTask("Обучение охраны работе с pass24.control", estimated_hours=3),
                TemplateTask("Рассылка инструкций жильцам по мобильному приложению"),
            ],
        ),
        TemplatePhase(
            order=7, name="UAT Testing", duration_days=10, weight=1,
            description="Тестирование всех сценариев доступа",
            tasks=[
                TemplateTask("Составить тест-план (20 сценариев)", estimated_hours=4),
                TemplateTask("Проход по всем КПП и точкам доступа", estimated_hours=8),
                TemplateTask("Фиксация и устранение багов", estimated_hours=16),
                TemplateTask("Regression testing"),
            ],
        ),
        TemplatePhase(
            order=8, name="Pilot Operation", duration_days=7, weight=1,
            description="Запуск для ограниченной группы жильцов",
            tasks=[
                TemplateTask("Запуск для 1 подъезда (pilot)"),
                TemplateTask("Сбор feedback от жильцов", estimated_hours=4),
                TemplateTask("Ежедневный мониторинг инцидентов", estimated_hours=6),
            ],
        ),
        TemplatePhase(
            order=9, name="Go-Live", duration_days=1, weight=2,
            description="Переключение всех подъездов на систему",
            tasks=[
                TemplateTask("Переключение всех подъездов на PASS24", is_milestone=True, estimated_hours=4),
                TemplateTask("Отправить приглашения всем жильцам"),
                TemplateTask("Дежурство инженера на объекте", estimated_hours=8),
            ],
        ),
        TemplatePhase(
            order=10, name="Handover", duration_days=5, weight=1,
            description="Сдача работ, передача паролей, начало поддержки",
            tasks=[
                TemplateTask("Подписать акт сдачи-приёмки", is_milestone=True, estimated_hours=2),
                TemplateTask("Передача административных паролей"),
                TemplateTask("Активация гарантийной поддержки в Service Desk"),
            ],
        ),
    ],
)


# ---------------------------------------------------------------------------
# Шаблон 2: Стандартный БЦ (commercial) — 9 фаз, ~8 недель
# ---------------------------------------------------------------------------

COMMERCIAL_TEMPLATE = TemplateDefinition(
    title="Стандартный БЦ",
    description="Внедрение PASS24 в бизнес-центре: шлагбаумы парковки, турникеты, интеграция с 1С/AD, ~8 недель.",
    phases=[
        TemplatePhase(
            order=1, name="Kickoff & Planning", duration_days=5, weight=1,
            description="Запуск проекта",
            tasks=[
                TemplateTask("Kickoff meeting с представителями БЦ", is_milestone=True, estimated_hours=3),
                TemplateTask("Согласовать контакты IT и охраны"),
                TemplateTask("Составить план работ с учётом рабочих часов БЦ"),
            ],
        ),
        TemplatePhase(
            order=2, name="Procurement", duration_days=14, weight=1,
            description="Закупка оборудования",
            tasks=[
                TemplateTask("Спецификация: турникеты, шлагбаумы, считыватели", estimated_hours=6),
                TemplateTask("Закупка оборудования"),
                TemplateTask("Подготовка монтажных материалов"),
            ],
        ),
        TemplatePhase(
            order=3, name="Hardware Installation", duration_days=14, weight=2,
            description="Монтаж турникетов в лобби, шлагбаумов на парковке",
            tasks=[
                TemplateTask("Установка турникетов в лобби", is_milestone=True, estimated_hours=24),
                TemplateTask("Монтаж шлагбаумов на парковке", estimated_hours=16),
                TemplateTask("Установка считывателей на этажах"),
                TemplateTask("Прокладка СКС"),
            ],
        ),
        TemplatePhase(
            order=4, name="Software Configuration", duration_days=10, weight=1,
            description="Настройка PASS24 + интеграция с 1С/AD",
            tasks=[
                TemplateTask("Создать объект в PASS24.online"),
                TemplateTask("Настроить турникеты и шлагбаумы"),
                TemplateTask("Интеграция с 1С/Active Directory", is_milestone=True, estimated_hours=16),
                TemplateTask("Настройка правил доступа по этажам"),
            ],
        ),
        TemplatePhase(
            order=5, name="Employee/Tenant Data Import", duration_days=7, weight=1,
            description="Импорт сотрудников арендаторов",
            tasks=[
                TemplateTask("Получить реестр арендаторов и сотрудников"),
                TemplateTask("Синхронизация с AD / 1С", estimated_hours=4),
                TemplateTask("Массовый импорт сотрудников"),
            ],
        ),
        TemplatePhase(
            order=6, name="Training", duration_days=5, weight=1,
            description="Отдельные тренинги ресепшн и охраны",
            tasks=[
                TemplateTask("Обучение сотрудников ресепшн", is_milestone=True, estimated_hours=3),
                TemplateTask("Обучение охраны", estimated_hours=3),
                TemplateTask("Подготовка памяток для арендаторов"),
            ],
        ),
        TemplatePhase(
            order=7, name="UAT Testing", duration_days=7, weight=1,
            description="Тестирование",
            tasks=[
                TemplateTask("Тест-план сценариев БЦ"),
                TemplateTask("Проход через все точки доступа"),
                TemplateTask("Тестирование интеграции с 1С/AD"),
            ],
        ),
        TemplatePhase(
            order=8, name="Go-Live", duration_days=1, weight=2,
            description="Ввод в эксплуатацию",
            tasks=[
                TemplateTask("Запуск всех точек доступа", is_milestone=True, estimated_hours=4),
                TemplateTask("Рассылка инструкций арендаторам"),
                TemplateTask("Дежурство инженера"),
            ],
        ),
        TemplatePhase(
            order=9, name="Handover", duration_days=3, weight=1,
            description="Сдача работ",
            tasks=[
                TemplateTask("Акт сдачи-приёмки", is_milestone=True, estimated_hours=2),
                TemplateTask("Передача паролей"),
                TemplateTask("Активация поддержки"),
            ],
        ),
    ],
)


# ---------------------------------------------------------------------------
# Шаблон 3: Только камеры (cameras_only) — 5 фаз, ~4 недели
# ---------------------------------------------------------------------------

CAMERAS_ONLY_TEMPLATE = TemplateDefinition(
    title="Только камеры (pass24.auto)",
    description="Минимальное внедрение: установка камер распознавания номеров для парковки, ~4 недели.",
    phases=[
        TemplatePhase(
            order=1, name="Planning", duration_days=3, weight=1,
            description="Обследование объекта, точки установки",
            tasks=[
                TemplateTask("Обследование объекта", is_milestone=True, estimated_hours=4),
                TemplateTask("Согласование точек установки камер"),
                TemplateTask("Составление спецификации"),
            ],
        ),
        TemplatePhase(
            order=2, name="Hardware Installation", duration_days=10, weight=2,
            description="Монтаж камер и сетевой инфраструктуры",
            tasks=[
                TemplateTask("Монтаж камер на точках парковки", is_milestone=True, estimated_hours=16),
                TemplateTask("Настройка сетевого оборудования", estimated_hours=4),
                TemplateTask("Тестирование видеопотоков", estimated_hours=4),
            ],
        ),
        TemplatePhase(
            order=3, name="pass24.auto Configuration", duration_days=7, weight=1,
            description="Настройка распознавания номеров",
            tasks=[
                TemplateTask("Настройка pass24.auto", estimated_hours=4),
                TemplateTask("Обучение моделей распознавания номеров", estimated_hours=8),
                TemplateTask("Настройка белых списков номеров"),
            ],
        ),
        TemplatePhase(
            order=4, name="Testing", duration_days=5, weight=1,
            description="Проверка точности распознавания",
            tasks=[
                TemplateTask("Тест распознавания 100 разных номеров", estimated_hours=4),
                TemplateTask("Валидация точности >95%", is_milestone=True, estimated_hours=2),
            ],
        ),
        TemplatePhase(
            order=5, name="Go-Live & Handover", duration_days=3, weight=2,
            description="Запуск и сдача работ",
            tasks=[
                TemplateTask("Запуск в эксплуатацию", is_milestone=True, estimated_hours=2),
                TemplateTask("Акт сдачи-приёмки", is_milestone=True, estimated_hours=2),
                TemplateTask("Передача паролей и активация поддержки"),
            ],
        ),
    ],
)


# ---------------------------------------------------------------------------
# Шаблон 4: Большая стройка (large_construction) — 12 фаз, ~16 недель
# ---------------------------------------------------------------------------

LARGE_CONSTRUCTION_TEMPLATE = TemplateDefinition(
    title="Большая стройка",
    description="Масштабный проект с тендером, поэтапной сдачей очередей, усиленным контролем качества, ~16 недель.",
    phases=[
        TemplatePhase(
            order=1, name="Kickoff & Planning", duration_days=7, weight=1,
            description="Запуск проекта, согласование с заказчиком и подрядчиками",
            tasks=[
                TemplateTask("Kickoff meeting с застройщиком", is_milestone=True, estimated_hours=4),
                TemplateTask("Согласование контактов всех сторон"),
                TemplateTask("Составление детального план-графика по очередям"),
            ],
        ),
        TemplatePhase(
            order=2, name="Extended Procurement", duration_days=28, weight=2,
            description="Тендер, закупка, логистика, входной контроль",
            tasks=[
                TemplateTask("Подготовка тендерной документации", estimated_hours=16),
                TemplateTask("Проведение тендера", is_milestone=True, estimated_hours=24),
                TemplateTask("Закупка оборудования", estimated_hours=8),
                TemplateTask("Логистика и доставка на объект", estimated_hours=8),
                TemplateTask("Входной контроль оборудования", estimated_hours=16),
            ],
        ),
        TemplatePhase(
            order=3, name="Site Preparation", duration_days=7, weight=1,
            description="Подготовка электрики и магистралей СКС",
            tasks=[
                TemplateTask("Прокладка магистральной СКС", estimated_hours=24),
                TemplateTask("Подключение электропитания к точкам", estimated_hours=16),
                TemplateTask("Подготовка монтажных поверхностей"),
            ],
        ),
        TemplatePhase(
            order=4, name="Hardware Installation", duration_days=35, weight=3,
            description="Поэтапный монтаж по очередям сдачи объекта",
            tasks=[
                TemplateTask("Монтаж очереди 1: СКУД на КПП", is_milestone=True, estimated_hours=32),
                TemplateTask("Монтаж очереди 2: подъезды секций А-Б", estimated_hours=40),
                TemplateTask("Монтаж очереди 3: подъезды секций В-Г", estimated_hours=40),
                TemplateTask("Монтаж парковочных шлагбаумов", estimated_hours=24),
                TemplateTask("Фотодокументирование каждой очереди"),
            ],
        ),
        TemplatePhase(
            order=5, name="Quality Inspection", duration_days=5, weight=1,
            description="Контроль качества монтажа по чек-листу",
            tasks=[
                TemplateTask("Чек-лист по всем точкам монтажа", estimated_hours=16),
                TemplateTask("Проверка кабельных трасс", estimated_hours=8),
                TemplateTask("Фиксация замечаний и их устранение", is_milestone=True, estimated_hours=16),
            ],
        ),
        TemplatePhase(
            order=6, name="Software Configuration", duration_days=14, weight=1,
            description="Настройка PASS24 для большого объекта",
            tasks=[
                TemplateTask("Создание объекта со всеми секциями"),
                TemplateTask("Настройка зон для каждой секции", estimated_hours=12),
                TemplateTask("Конфигурация правил доступа", estimated_hours=8),
            ],
        ),
        TemplatePhase(
            order=7, name="User Data Import", duration_days=7, weight=1,
            description="Массовый импорт жильцов по очередям",
            tasks=[
                TemplateTask("Получить списки жильцов по каждой очереди"),
                TemplateTask("Поэтапная загрузка (каждая очередь отдельно)", is_milestone=True, estimated_hours=8),
                TemplateTask("QA всех загруженных учёток", estimated_hours=8),
            ],
        ),
        TemplatePhase(
            order=8, name="Training", duration_days=7, weight=1,
            description="Обучение УК и охраны",
            tasks=[
                TemplateTask("Тренинг УК", is_milestone=True, estimated_hours=6),
                TemplateTask("Обучение охраны всех КПП", estimated_hours=6),
                TemplateTask("Рассылка инструкций жильцам"),
            ],
        ),
        TemplatePhase(
            order=9, name="UAT Testing", duration_days=10, weight=1,
            description="Комплексное тестирование",
            tasks=[
                TemplateTask("Тест-план: 30+ сценариев", estimated_hours=6),
                TemplateTask("Прохождение всех КПП и точек", estimated_hours=16),
                TemplateTask("Стресс-тесты в часы пик", estimated_hours=8),
            ],
        ),
        TemplatePhase(
            order=10, name="Pilot Operation", duration_days=14, weight=1,
            description="Запуск для первой очереди",
            tasks=[
                TemplateTask("Pilot запуск очереди 1"),
                TemplateTask("Ежедневный мониторинг", estimated_hours=16),
                TemplateTask("Feedback от жильцов первой очереди"),
            ],
        ),
        TemplatePhase(
            order=11, name="Go-Live", duration_days=2, weight=2,
            description="Ввод в эксплуатацию всех очередей",
            tasks=[
                TemplateTask("Запуск всех очередей", is_milestone=True, estimated_hours=8),
                TemplateTask("Дежурство инженеров на всех КПП", estimated_hours=16),
            ],
        ),
        TemplatePhase(
            order=12, name="Handover", duration_days=7, weight=1,
            description="Сдача работ",
            tasks=[
                TemplateTask("Акт сдачи-приёмки", is_milestone=True, estimated_hours=4),
                TemplateTask("Передача всей документации"),
                TemplateTask("Активация расширенной поддержки"),
            ],
        ),
    ],
)


# ---------------------------------------------------------------------------
# Реестр всех шаблонов
# ---------------------------------------------------------------------------

PROJECT_TEMPLATES: Dict[ProjectType, TemplateDefinition] = {
    ProjectType.RESIDENTIAL: RESIDENTIAL_TEMPLATE,
    ProjectType.COMMERCIAL: COMMERCIAL_TEMPLATE,
    ProjectType.CAMERAS_ONLY: CAMERAS_ONLY_TEMPLATE,
    ProjectType.LARGE_CONSTRUCTION: LARGE_CONSTRUCTION_TEMPLATE,
}


def get_template(project_type: ProjectType) -> TemplateDefinition:
    """Вернуть шаблон по типу проекта."""
    template = PROJECT_TEMPLATES.get(project_type)
    if template is None:
        raise ValueError(f"Неизвестный тип проекта: {project_type}")
    return template

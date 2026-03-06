/**
 * Global app state for view mode, calendar sub-view, selected day, and focus.
 */
export type ViewMode = 'calendar' | 'todo';
export type CalendarView = 'day' | 'month';
export type CalendarDensity = 'minimal' | 'balanced' | 'dense';
export type TodoOrder = 'oldest' | 'newest';

class AppStore {
  viewMode = $state<ViewMode>('calendar');
  calendarView = $state<CalendarView>('month');
  calendarDensity = $state<CalendarDensity>('balanced');
  showTodosOnCalendar = $state<boolean>(true);
  /** When false, hide completed todos in the todo list view */
  showCompletedTodos = $state<boolean>(true);
  /** Todo list order: oldest first (by due) or newest first */
  todoOrder = $state<TodoOrder>('oldest');
  selectedDate = $state<Date>(new Date(new Date().getFullYear(), new Date().getMonth(), new Date().getDate()));
  focusedEventIndex = $state<number>(-1);
  focusedTodoIndex = $state<number>(-1);
  focusedDayIndex = $state<number>(-1);
  /** Date for the currently focused day cell (month view); used for Enter → day view */
  focusedDayDate = $state<Date | null>(null);
  modalOpen = $state<'event' | 'todo' | 'shortcuts' | null>(null);
  editingId = $state<string | null>(null);
  hasUnsyncedChanges = $state(false);
  /** IANA timezone (e.g. America/New_York) or empty string for browser local */
  timezone = $state<string>('');
  /** Calendar height as ratio of container width (0.5 = 50%, 2 = 200%). Used for manual height control. */
  calendarHeightRatio = $state<number>(1);
  /** When true, navbar is collapsed; hover at top to show again. */
  navbarCollapsed = $state<boolean>(false);

  setViewMode(mode: ViewMode) {
    this.viewMode = mode;
  }

  setCalendarView(cv: CalendarView) {
    this.calendarView = cv;
  }

  setCalendarDensity(density: CalendarDensity) {
    this.calendarDensity = density;
  }

  cycleCalendarDensity() {
    const order: CalendarDensity[] = ['minimal', 'balanced', 'dense'];
    const i = order.indexOf(this.calendarDensity);
    this.calendarDensity = order[(i + 1) % order.length];
  }

  setShowTodosOnCalendar(show: boolean) {
    this.showTodosOnCalendar = show;
  }

  toggleShowTodosOnCalendar() {
    this.showTodosOnCalendar = !this.showTodosOnCalendar;
  }

  setShowCompletedTodos(show: boolean) {
    this.showCompletedTodos = show;
  }

  toggleShowCompletedTodos() {
    this.showCompletedTodos = !this.showCompletedTodos;
  }

  setTodoOrder(order: TodoOrder) {
    this.todoOrder = order;
  }

  setSelectedDate(d: Date) {
    this.selectedDate = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  }

  goToToday() {
    this.setSelectedDate(new Date());
  }

  setFocusedEventIndex(i: number) {
    this.focusedEventIndex = i;
  }

  setFocusedTodoIndex(i: number) {
    this.focusedTodoIndex = i;
  }

  setFocusedDayIndex(i: number) {
    this.focusedDayIndex = i;
  }

  setFocusedDayDate(d: Date | null) {
    this.focusedDayDate = d;
  }

  setModalOpen(m: 'event' | 'todo' | 'shortcuts' | null) {
    this.modalOpen = m;
  }

  setEditingId(id: string | null) {
    this.editingId = id;
  }

  setUnsyncedChanges(unsynced: boolean) {
    this.hasUnsyncedChanges = unsynced;
  }

  setTimezone(tz: string) {
    this.timezone = tz;
  }

  setCalendarHeightRatio(ratio: number) {
    const r = Math.max(0.5, Math.min(2, ratio));
    this.calendarHeightRatio = r;
    if (typeof localStorage !== 'undefined') localStorage.setItem('calslop-calendar-height-ratio', String(r));
  }

  setNavbarCollapsed(collapsed: boolean) {
    this.navbarCollapsed = collapsed;
    if (typeof localStorage !== 'undefined') localStorage.setItem('calslop-navbar-collapsed', collapsed ? '1' : '0');
  }

  resetFocus() {
    this.focusedEventIndex = -1;
    this.focusedTodoIndex = -1;
    this.focusedDayIndex = -1;
  }
}

export const app = new AppStore();

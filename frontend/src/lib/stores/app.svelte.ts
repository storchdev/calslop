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
  showCompletedTodos = $state<boolean>(false);
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
  pendingApiRequests = $state(0);
  apiLoading = $state(false);
  /** IANA timezone (e.g. America/New_York) or empty string for browser local */
  timezone = $state<string>('');
  /** Calendar height ratio (1 = 100%, 3 = 300%). Used for manual height control. */
  calendarHeightRatio = $state<number>(1);
  /** When true, navbar is collapsed; hover at top to show again. */
  navbarCollapsed = $state<boolean>(false);
  /** Search: text in the search input (month view / todo view). */
  searchInputValue = $state<string>('');
  /** Search: applied filter (set on Enter); used to highlight days or filter todo list. */
  searchQuery = $state<string>('');
  /** Month view search mode: cell indices of days that match the search (set by Calendar). */
  highlightedDayIndices = $state<number[]>([]);
  private apiHideTimer: ReturnType<typeof setTimeout> | null = null;

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

  startApiRequest() {
    if (this.apiHideTimer) {
      clearTimeout(this.apiHideTimer);
      this.apiHideTimer = null;
    }
    this.pendingApiRequests += 1;
    this.apiLoading = true;
  }

  endApiRequest() {
    this.pendingApiRequests = Math.max(0, this.pendingApiRequests - 1);
    if (this.pendingApiRequests > 0) return;
    this.apiHideTimer = setTimeout(() => {
      this.apiLoading = false;
      this.apiHideTimer = null;
    }, 220);
  }

  setTimezone(tz: string) {
    this.timezone = tz;
  }

  setCalendarHeightRatio(ratio: number) {
    const r = Math.max(1, Math.min(3, ratio));
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

  setSearchInputValue(v: string) {
    this.searchInputValue = v;
  }

  setSearchQuery(q: string) {
    this.searchQuery = q;
  }

  /** Clear search input and applied query (Escape). */
  clearSearch() {
    this.searchInputValue = '';
    this.searchQuery = '';
  }

  /** Apply current input value as search filter (Enter). */
  applySearch() {
    this.searchQuery = this.searchInputValue.trim();
  }

  setHighlightedDayIndices(indices: number[]) {
    this.highlightedDayIndices = indices;
  }
}

export const app = new AppStore();

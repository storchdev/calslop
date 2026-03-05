/**
 * Global app state for view mode, calendar sub-view, selected day, and focus.
 */
export type ViewMode = 'calendar' | 'todo';
export type CalendarView = 'day' | 'month';

class AppStore {
  viewMode = $state<ViewMode>('calendar');
  calendarView = $state<CalendarView>('month');
  selectedDate = $state<Date>(new Date(new Date().getFullYear(), new Date().getMonth(), new Date().getDate()));
  focusedEventIndex = $state<number>(-1);
  focusedTodoIndex = $state<number>(-1);
  focusedDayIndex = $state<number>(-1);
  modalOpen = $state<'event' | 'todo' | 'shortcuts' | null>(null);
  editingId = $state<string | null>(null);

  setViewMode(mode: ViewMode) {
    this.viewMode = mode;
  }

  setCalendarView(cv: CalendarView) {
    this.calendarView = cv;
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

  setModalOpen(m: 'event' | 'todo' | 'shortcuts' | null) {
    this.modalOpen = m;
  }

  setEditingId(id: string | null) {
    this.editingId = id;
  }

  resetFocus() {
    this.focusedEventIndex = -1;
    this.focusedTodoIndex = -1;
    this.focusedDayIndex = -1;
  }
}

export const app = new AppStore();

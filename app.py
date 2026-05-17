import threading
import tkinter as tk
from tkinter import messagebox, ttk

from classifier import classify_message
from database import add_ticket, get_recent_tickets, init_db, update_ticket_status
from knowledge_base import find_relevant_knowledge
from llm_agent import generate_support_answer, get_openrouter_client


class SupportApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("LLM-агент технической поддержки")
        self.geometry("1360x900")
        self.minsize(1200, 820)

        self.current_ticket_id: int | None = None
        self.current_answer = ""
        self.is_processing = False

        init_db()
        self.configure_styles()
        self.create_widgets()
        self.update_api_mode()
        self.refresh_recent_tickets()

    def configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10))
        style.configure("TButton", padding=(10, 6))
        style.configure("TLabelframe", padding=8)
        style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        style.configure("Title.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10))
        style.configure("Status.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", rowheight=24, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def create_widgets(self) -> None:
        main = ttk.Frame(self, padding=10)
        main.pack(fill=tk.BOTH, expand=True)
        main.rowconfigure(1, weight=8)
        main.rowconfigure(2, weight=0)
        main.columnconfigure(0, weight=1)

        self.create_header(main)

        content = ttk.Frame(main)
        content.grid(row=1, column=0, sticky="nsew", pady=(10, 8))
        content.rowconfigure(0, weight=1)
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=3)

        left = ttk.Frame(content)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        right = ttk.Frame(content)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=0)
        right.rowconfigure(1, weight=0)
        right.rowconfigure(2, weight=5, minsize=330)
        right.columnconfigure(0, weight=1)

        self.create_input_block(left)
        self.create_dialog_block(left)
        self.create_analysis_block(right)
        self.create_knowledge_block(right)
        self.create_answer_block(right)
        self.create_journal_block(main)

    def create_header(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent, padding=(2, 0, 2, 2))
        frame.grid(row=0, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)

        ttk.Label(
            frame,
            text="LLM-агент технической поддержки",
            style="Title.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            frame,
            text="Автоматическая классификация обращений, поиск инструкции и генерация ответа",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 6))

        self.mode_var = tk.StringVar(value="Режим работы: Fallback-режим")
        self.status_var = tk.StringVar(value="Статус: готово")

        ttk.Label(frame, textvariable=self.mode_var).grid(row=2, column=0, sticky="w")
        ttk.Label(frame, textvariable=self.status_var, style="Status.TLabel").grid(
            row=3, column=0, sticky="w", pady=(2, 0)
        )

    def create_input_block(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Обращение пользователя", padding=10)
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(0, weight=1)

        self.message_text = tk.Text(
            frame,
            height=5,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            undo=True,
        )
        self.message_text.grid(row=0, column=0, columnspan=2, sticky="ew")

        self.generate_button = ttk.Button(
            frame,
            text="Сгенерировать ответ",
            command=self.process_message,
        )
        self.generate_button.grid(row=1, column=0, sticky="ew", pady=(8, 0), padx=(0, 4))

        self.clear_button = ttk.Button(
            frame,
            text="Очистить",
            command=self.clear_input,
        )
        self.clear_button.grid(row=1, column=1, sticky="ew", pady=(8, 0), padx=(4, 0))

    def create_dialog_block(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Диалог", padding=10)
        frame.grid(row=1, column=0, sticky="nsew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.chat_history = tk.Text(
            frame,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Segoe UI", 10),
            padx=8,
            pady=8,
        )
        self.chat_history.grid(row=0, column=0, sticky="nsew")
        self.chat_history.tag_configure("user_label", font=("Segoe UI", 10, "bold"))
        self.chat_history.tag_configure("assistant_label", font=("Segoe UI", 10, "bold"))
        self.chat_history.tag_configure("user_text", foreground="#1f2937")
        self.chat_history.tag_configure("assistant_text", foreground="#374151")
        self.chat_history.tag_configure("separator", foreground="#9ca3af")

        scrollbar = ttk.Scrollbar(frame, command=self.chat_history.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.chat_history.configure(yscrollcommand=scrollbar.set)

    def create_analysis_block(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Анализ обращения", padding=10)
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        frame.columnconfigure(1, weight=1)

        self.category_var = tk.StringVar(value="-")
        self.priority_var = tk.StringVar(value="-")
        self.specialist_var = tk.StringVar(value="-")
        self.summary_var = tk.StringVar(value="-")

        ttk.Label(frame, text="Категория:").grid(row=0, column=0, sticky="nw", pady=2)
        ttk.Label(frame, textvariable=self.category_var, wraplength=380).grid(
            row=0, column=1, sticky="ew", pady=2
        )

        ttk.Label(frame, text="Приоритет:").grid(row=1, column=0, sticky="nw", pady=2)
        self.priority_label = ttk.Label(frame, textvariable=self.priority_var)
        self.priority_label.grid(row=1, column=1, sticky="ew", pady=2)

        ttk.Label(frame, text="Требуется специалист:").grid(row=2, column=0, sticky="nw", pady=2)
        ttk.Label(frame, textvariable=self.specialist_var).grid(
            row=2, column=1, sticky="ew", pady=2
        )

        ttk.Label(frame, text="Краткое описание:").grid(row=3, column=0, sticky="nw", pady=2)
        ttk.Label(frame, textvariable=self.summary_var, wraplength=380).grid(
            row=3, column=1, sticky="ew", pady=2
        )

    def create_knowledge_block(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Найденная инструкция", padding=10)
        frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.knowledge_text = tk.Text(
            frame,
            height=5,
            wrap=tk.WORD,
            font=("Segoe UI", 9),
            padx=8,
            pady=6,
        )
        self.knowledge_text.grid(row=0, column=0, sticky="ew")
        self.knowledge_text.configure(state=tk.DISABLED)

        scrollbar = ttk.Scrollbar(frame, command=self.knowledge_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.knowledge_text.configure(yscrollcommand=scrollbar.set)

    def create_answer_block(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Ответ для пользователя", padding=10)
        frame.grid(row=2, column=0, sticky="nsew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.answer_text = tk.Text(
            frame,
            height=12,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            padx=8,
            pady=8,
        )
        self.answer_text.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(frame, command=self.answer_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.answer_text.configure(yscrollcommand=scrollbar.set)

        actions = ttk.Frame(frame)
        actions.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)

        self.send_button = ttk.Button(
            actions,
            text="Отправить пользователю",
            command=self.confirm_answer,
        )
        self.send_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self.transfer_button = ttk.Button(
            actions,
            text="Передать специалисту",
            command=self.transfer_to_specialist,
        )
        self.transfer_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))

    def create_journal_block(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Журнал обращений", padding=10)
        frame.grid(row=2, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)

        columns = (
            "id",
            "created_at",
            "category",
            "priority",
            "specialist",
            "status",
            "message",
        )
        self.recent_tree = ttk.Treeview(frame, columns=columns, show="headings", height=4)
        headings = {
            "id": "ID",
            "created_at": "Дата",
            "category": "Категория",
            "priority": "Приоритет",
            "specialist": "Специалист",
            "status": "Статус",
            "message": "Текст обращения",
        }
        widths = {
            "id": 45,
            "created_at": 140,
            "category": 115,
            "priority": 90,
            "specialist": 90,
            "status": 180,
            "message": 500,
        }
        for column in columns:
            self.recent_tree.heading(column, text=headings[column])
            self.recent_tree.column(column, width=widths[column], anchor=tk.W)

        self.recent_tree.grid(row=0, column=0, sticky="ew")
        scrollbar = ttk.Scrollbar(frame, command=self.recent_tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.recent_tree.configure(yscrollcommand=scrollbar.set)

    def update_api_mode(self, connected: bool | None = None) -> None:
        if connected is None:
            connected = get_openrouter_client() is not None

        if connected:
            self.mode_var.set("Режим работы: OpenRouter API подключен")
        else:
            self.mode_var.set("Режим работы: Fallback-режим")

    def set_status(self, text: str) -> None:
        self.status_var.set(f"Статус: {text}")
        self.update_idletasks()

    def clear_input(self) -> None:
        self.message_text.delete("1.0", tk.END)

    def process_message(self) -> None:
        if self.is_processing:
            return

        user_message = self.message_text.get("1.0", tk.END).strip()
        if not user_message:
            messagebox.showwarning("Пустое обращение", "Введите текст обращения пользователя.")
            return

        self.set_processing_state(True)
        thread = threading.Thread(
            target=self.process_message_worker,
            args=(user_message,),
            daemon=True,
        )
        thread.start()

    def process_message_worker(self, user_message: str) -> None:
        try:
            self.after(0, self.set_status, "анализ обращения...")
            classification = classify_message(user_message)
            category = classification["category"]
            priority = classification["priority"]
            need_operator = classification["need_operator"]
            summary = classification["summary"]

            self.after(0, self.set_status, "поиск инструкции в базе знаний...")
            knowledge_context = find_relevant_knowledge(user_message, category)

            self.after(0, self.set_status, "генерация ответа...")
            llm_answer = generate_support_answer(
                user_message=user_message,
                category=category,
                priority=priority,
                need_operator=need_operator,
                knowledge_context=knowledge_context,
            )

            if llm_answer:
                answer = llm_answer
                status = "Сгенерировано"
                api_connected = True
                final_status = "готово"
            else:
                answer = (
                    "Не удалось получить ответ от LLM. Проверьте файл .env, "
                    "API-ключ OpenRouter, доступность модели и интернет-соединение."
                )
                status = "Ошибка LLM"
                api_connected = False
                final_status = "API недоступен, использован fallback-режим"

            ticket_id = add_ticket(
                user_message=user_message,
                category=category,
                priority=priority,
                need_operator=need_operator,
                generated_answer=answer,
                status=status,
            )

            self.after(
                0,
                self.apply_processed_result,
                ticket_id,
                user_message,
                classification,
                knowledge_context,
                answer,
                api_connected,
                final_status,
            )
        except Exception as exc:
            self.after(0, self.show_processing_error, exc)

    def apply_processed_result(
        self,
        ticket_id: int,
        user_message: str,
        classification: dict,
        knowledge_context: str,
        answer: str,
        api_connected: bool,
        final_status: str,
    ) -> None:
        self.current_ticket_id = ticket_id
        self.current_answer = answer

        self.update_api_mode(api_connected)
        self.show_classification(
            classification["category"],
            classification["priority"],
            classification["need_operator"],
            classification["summary"],
        )
        self.show_knowledge(knowledge_context)
        self.show_answer(answer)
        self.add_chat_record(user_message, answer)
        self.refresh_recent_tickets()
        self.set_status(final_status)
        self.set_processing_state(False)

    def show_processing_error(self, exc: Exception) -> None:
        self.set_processing_state(False)
        self.update_api_mode(False)
        self.set_status("API недоступен, использован fallback-режим")
        messagebox.showerror("Ошибка обработки", f"Не удалось обработать обращение:\n{exc}")

    def set_processing_state(self, is_processing: bool) -> None:
        self.is_processing = is_processing
        self.configure(cursor="watch" if is_processing else "")
        state = tk.DISABLED if is_processing else tk.NORMAL
        self.generate_button.configure(state=state)
        self.clear_button.configure(state=state)
        self.send_button.configure(state=state)
        self.transfer_button.configure(state=state)

    def show_classification(
        self,
        category: str,
        priority: str,
        need_operator: bool,
        summary: str,
    ) -> None:
        self.category_var.set(category)
        self.priority_var.set(priority)
        self.specialist_var.set("Да" if need_operator else "Нет")
        self.summary_var.set(summary)

        priority_colors = {
            "Низкий": "#16803a",
            "Средний": "#b45309",
            "Высокий": "#dc2626",
        }
        self.priority_label.configure(foreground=priority_colors.get(priority, "#111827"))

    def show_knowledge(self, knowledge_context: str) -> None:
        self.knowledge_text.configure(state=tk.NORMAL)
        self.knowledge_text.delete("1.0", tk.END)
        self.knowledge_text.insert("1.0", knowledge_context)
        self.knowledge_text.configure(state=tk.DISABLED)

    def show_answer(self, answer: str) -> None:
        self.answer_text.delete("1.0", tk.END)
        self.answer_text.insert("1.0", answer)

    def add_chat_record(self, user_message: str, answer: str) -> None:
        self.chat_history.configure(state=tk.NORMAL)
        self.chat_history.insert(tk.END, "Пользователь:\n", "user_label")
        self.chat_history.insert(tk.END, f"{user_message}\n\n", "user_text")
        self.chat_history.insert(tk.END, "AI-ассистент:\n", "assistant_label")
        self.chat_history.insert(tk.END, f"{answer}\n\n", "assistant_text")
        self.chat_history.insert(tk.END, "-" * 50 + "\n\n", "separator")
        self.chat_history.configure(state=tk.DISABLED)
        self.chat_history.see(tk.END)

    def confirm_answer(self) -> None:
        self.update_current_status("Отправлено пользователю", "Ответ отправлен пользователю.")

    def transfer_to_specialist(self) -> None:
        self.update_current_status("Передано специалисту", "Обращение передано специалисту.")

    def update_current_status(self, status: str, info_message: str) -> None:
        if self.current_ticket_id is None:
            messagebox.showinfo("Нет обращения", "Сначала обработайте обращение пользователя.")
            return

        update_ticket_status(self.current_ticket_id, status)
        self.refresh_recent_tickets()
        self.set_status("готово")
        messagebox.showinfo("Статус обновлен", info_message)

    def refresh_recent_tickets(self) -> None:
        for item in self.recent_tree.get_children():
            self.recent_tree.delete(item)

        for ticket in get_recent_tickets(limit=10):
            message = ticket["user_message"].replace("\n", " ")
            if len(message) > 80:
                message = message[:77] + "..."

            self.recent_tree.insert(
                "",
                tk.END,
                values=(
                    ticket["id"],
                    ticket["created_at"],
                    ticket["category"],
                    ticket["priority"],
                    "Да" if ticket["need_operator"] else "Нет",
                    ticket["status"],
                    message,
                ),
            )


if __name__ == "__main__":
    app = SupportApp()
    app.mainloop()

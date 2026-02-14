"use client";

import { type Mode } from "@/lib/api";

const MODES: { value: Mode; label: string }[] = [
    { value: "work", label: "Work" },
    { value: "date", label: "Date" },
    { value: "quick_bite", label: "Quick Bite" },
    { value: "budget", label: "Budget" },
]

interface ModeSelectorProps {
    mode: Mode;
    onModeChange: (mode: Mode) => void;
}

export default function ModeSelector({ mode, onModeChange }: ModeSelectorProps) {
    return (
        <div className="flex flex-wrap gap-2" role="group" aria-label="Recommendation mode selector">
            {MODES.map(({ value, label }) => (
                <button
                    key={value}
                    type="button"
                    onClick={() => onModeChange(value)}
                    aria-pressed={mode === value}
                    className={
                        mode === value
                            // ? "bg-blue-600 text-white px-4 py-2 rounded"
                            // : "bg-gray-200 text-gray-700 px-4 py-2 rounded hover:bg-gray-300"
                            ? "rounded-full bg-foreground px-4 py-2 text-sm font-medium text-background"
                            : "rounded-full border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-700 hover:border-zinc-400 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:border-zinc-500"
                    }
                >
                    {label}
                </button>
            ))}
        </div>
    );
}
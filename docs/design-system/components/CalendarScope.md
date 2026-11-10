# CalendarScope

The region filter above the calendar: a labelled native `<select>` with a submit button. It works without JavaScript as a GET form.

**Source:** `frontend/src/app/CalendarScope.tsx`, styled by `.calendar-scope` in `calendar.css`. The same card shows `calendar-notice`, the calendar's error state.

## What the consumer supplies
The city catalogue (`cityCatalog`), with *Koko Suomi* as the empty value, and the current `period` for the form action.

## Rules
- The label (*Alue*) sits above the field, at weight 650. The select is 44px tall, at most 24rem wide, `product-surface` with a `product-border` outline and `button-radius`.
- The button sits beside the select and wraps below it under 650px. Its label names the result (*Näytä kalenteri*).
- The focus ring is 3px `product-primary`.

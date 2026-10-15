package com.agentworkspace.mobile.embedded

import android.content.Context
import android.view.View
import android.view.ViewGroup
import android.widget.BaseAdapter
import android.widget.Filter
import android.widget.Filterable
import android.widget.LinearLayout
import android.widget.TextView
import com.agentworkspace.mobile.UiText

/**
 * Model suggestions for the model name field: the id with what the provider says it can do under
 * it. Typing filters by any part of the id or name ("sonnet" finds "anthropic/claude-sonnet-5-5"),
 * which a prefix filter would not; picking one fills in the id.
 */
class ModelSuggestionAdapter(
    private val context: Context,
    private val all: List<ProviderModelCatalog.Model>,
) : BaseAdapter(), Filterable {
    private var shown: List<ProviderModelCatalog.Model> = all

    override fun getCount() = shown.size
    override fun getItem(position: Int): ProviderModelCatalog.Model = shown[position]
    override fun getItemId(position: Int) = position.toLong()

    fun tags(model: ProviderModelCatalog.Model): String = listOfNotNull(
        model.name,
        UiText.of(context, "看图", "Vision").takeIf { model.vision == true },
        UiText.of(context, "工具调用", "Tools").takeIf { model.tools == true },
        UiText.of(context, "推理", "Reasoning").takeIf { model.reasoning == true },
        model.contextTokens?.let { tokens ->
            val size = if (tokens >= 1_000_000) "${tokens / 1_000_000}M" else "${tokens / 1000}K"
            UiText.of(context, "$size 上下文", "$size context")
        },
    ).joinToString(" · ")

    override fun getView(position: Int, convertView: View?, parent: ViewGroup): View {
        val density = context.resources.displayMetrics.density
        val row = (convertView as? LinearLayout) ?: LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding((16 * density).toInt(), (10 * density).toInt(), (16 * density).toInt(), (10 * density).toInt())
            addView(TextView(context).apply { textSize = 15f; setSingleLine(true) })
            addView(TextView(context).apply { textSize = 12f; alpha = 0.7f; setSingleLine(true) })
        }
        val model = getItem(position)
        (row.getChildAt(0) as TextView).text = model.id
        val detail = row.getChildAt(1) as TextView
        detail.text = tags(model)
        detail.visibility = if (detail.text.isEmpty()) View.GONE else View.VISIBLE
        return row
    }

    override fun getFilter(): Filter = object : Filter() {
        override fun performFiltering(constraint: CharSequence?): FilterResults {
            val query = constraint?.toString()?.trim()?.lowercase().orEmpty()
            val matches = if (query.isEmpty()) all else all.filter {
                it.id.lowercase().contains(query) || it.name?.lowercase()?.contains(query) == true
            }
            return FilterResults().apply { values = matches; count = matches.size }
        }

        @Suppress("UNCHECKED_CAST")
        override fun publishResults(constraint: CharSequence?, results: FilterResults?) {
            shown = (results?.values as? List<ProviderModelCatalog.Model>) ?: all
            notifyDataSetChanged()
        }

        override fun convertResultToString(resultValue: Any?): CharSequence =
            (resultValue as? ProviderModelCatalog.Model)?.id ?: ""
    }
}

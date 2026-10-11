import 'package:flutter/material.dart';

class MessageCard extends StatelessWidget {
  final String text;
  final bool error;
  final VoidCallback? retry;
  const MessageCard(this.text, {super.key, this.error = false, this.retry});
  @override
  Widget build(BuildContext context) => Card(
    color: error ? const Color(0xffffeeee) : const Color(0xffe7f3f1),
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            text,
            style: TextStyle(
              color: error ? const Color(0xff922020) : const Color(0xff123e3b),
            ),
          ),
          if (retry != null)
            TextButton(onPressed: retry, child: const Text('Réessayer')),
        ],
      ),
    ),
  );
}

class PageBody extends StatelessWidget {
  final List<Widget> children;
  final Future<void> Function()? refresh;
  const PageBody({super.key, required this.children, this.refresh});
  @override
  Widget build(BuildContext context) {
    final list = ListView(
      padding: const EdgeInsets.all(20),
      physics: const AlwaysScrollableScrollPhysics(),
      children: children
          .map(
            (w) =>
                Padding(padding: const EdgeInsets.only(bottom: 16), child: w),
          )
          .toList(),
    );
    return refresh == null
        ? list
        : RefreshIndicator(
            onRefresh: () async {
              try {
                await refresh!();
              } catch (_) {
                /* L'état d'erreur est affiché par le FutureBuilder. */
              }
            },
            child: list,
          );
  }
}

class ActionButton extends StatelessWidget {
  final String label;
  final VoidCallback? onPressed;
  final bool busy;
  const ActionButton(
    this.label, {
    super.key,
    this.onPressed,
    this.busy = false,
  });
  @override
  Widget build(BuildContext context) => FilledButton(
    onPressed: busy ? null : onPressed,
    style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
    child: busy
        ? const SizedBox(
            width: 22,
            height: 22,
            child: CircularProgressIndicator(strokeWidth: 2),
          )
        : Text(label),
  );
}

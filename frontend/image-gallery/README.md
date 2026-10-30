# Image preview ribbon

A ComfyUI frontend extension that pins a strip of recent output images along the bottom of the
graph. It reads the latest `/history` entries and renders thumbnails through ComfyUI's `/view`
endpoint, refreshing when a queued graph finishes. Clicking a thumbnail opens it full size with a
download link; the ribbon collapses to a title bar and does not poll while nothing is executing.

It reads at most the latest 80 history entries, skips ComfyUI's transient `temp` previews, and
never scans the output directory.

document.addEventListener("DOMContentLoaded", function(){
    window.setTimeout(()=>{
        document.addEventListener('keydown', function(event) {
            const key = event.key;
            const prev_link = document.getElementById('prev-link')
            const next_link = document.getElementById('next-link')
            if (key === "ArrowLeft" && prev_link !== null) {
                prev_link.click();
            } else if (key === "ArrowRight" && next_link !== null) {
                next_link.click();
            }
        });
    }, 1000);

    const primary = document.getElementById("page-tray");
    if (primary !== null) {
        var mc = new Hammer(primary, {
            domEvents: true,
        });

        mc.on("swipeleft swiperight", function(ev) {
            const prev_link = document.getElementById('prev-link')
            const next_link = document.getElementById('next-link')
            if (ev.type === "swiperight" && prev_link !== null) {
                prev_link.click();
            } else if (ev.type === "swipeleft" && next_link !== null) {
                next_link.click();
            }

        });
        mc.get('pinch').set({ enable: false });
    }
});

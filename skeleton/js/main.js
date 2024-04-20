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
});

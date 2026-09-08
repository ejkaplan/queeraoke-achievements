import pygame
import pygame.locals
from pytweening import easeInOutCubic
from time import monotonic
from multiprocessing import Process, Queue


def render_wrapped_text(
    text: str, font: pygame.Font, colour: str, allowed_width: float
):
    # first, split the text into words
    words = text.split()

    # now, construct lines out of these words
    lines = []
    while len(words) > 0:
        # get as many words as will fit within allowed_width
        line_words = []
        while len(words) > 0:
            line_words.append(words.pop(0))
            fw, fh = font.size(" ".join(line_words + words[:1]))
            if fw > allowed_width:
                break

        # add a line consisting of those words
        line = " ".join(line_words)
        lines.append(line)

    # now we've split our text into lines that fit into the width, actually
    # render them

    # we'll render each line below the last, so we need to keep track of
    # the culmative height of the lines we've rendered so far
    surface_height = sum(font.size(line)[1] for line in lines)
    surface_width = max(font.size(line)[0] for line in lines)
    surface = pygame.Surface((surface_width, surface_height), pygame.SRCALPHA)
    y_offset = 0
    for line in lines:
        fw, fh = font.size(line)

        font_surface = font.render(line, True, colour)
        surface.blit(font_surface, ((surface_width - fw) / 2, y_offset))

        y_offset += fh
    return surface


class Achievement:

    def __init__(
        self,
        width: float,
        height: float,
        text: str,
        font: pygame.Font,
        icon: pygame.Surface,
        fade_duration: float = 0.5,
        grow_duration: float = 1.0,
        hold_duration: float = 3.0,
    ):
        self.width = width
        self.height = height
        self.active = False
        self.done = False
        self.text_surface = render_wrapped_text(text, font, "#000000", width - height)
        if self.text_surface.get_height() > self.height:
            print("Too much text!")
            self.done = True
            return

        self.icon = pygame.transform.scale(
            icon, (int(0.6 * self.height), int(0.6 * self.height))
        )

        self.start_time = 0
        self.fade_in_time = fade_duration
        self.grow_time = self.fade_in_time + grow_duration
        self.hold_time = self.grow_time + hold_duration
        self.shrink_time = self.hold_time + grow_duration
        self.fade_out_time = self.shrink_time + fade_duration

    def start(self):
        if self.done:
            return
        self.start_time = monotonic()
        self.fade_in_time += self.start_time
        self.grow_time += self.start_time
        self.hold_time += self.start_time
        self.shrink_time += self.start_time
        self.fade_out_time += self.start_time
        self.active = True

    def render(self, screen: pygame.Surface):
        buffer_surface = pygame.Surface(screen.size, pygame.SRCALPHA)

        if not self.active:
            return
        curr_time = monotonic()
        if curr_time < self.fade_in_time:
            alpha = (curr_time - self.start_time) / (
                self.fade_in_time - self.start_time
            )
            t = 0
        elif curr_time < self.grow_time:
            alpha = 1
            t = (curr_time - self.fade_in_time) / (self.grow_time - self.fade_in_time)
        elif curr_time < self.hold_time:
            alpha = 1
            t = 1
        elif curr_time < self.shrink_time:
            alpha = 1
            t = (self.shrink_time - curr_time) / (self.shrink_time - self.hold_time)
        elif curr_time < self.fade_out_time:
            alpha = (self.fade_out_time - curr_time) / (
                self.fade_out_time - self.shrink_time
            )
            t = 0
        else:
            self.active = False
            self.done = True
            return

        t = max(0, min(t, 1))
        t = easeInOutCubic(t)

        x = 0.5 * screen.get_width()
        y = 0.5 * screen.get_height()

        rect_width_0, rect_width_1 = self.height, self.width
        rect_width = (1 - t) * rect_width_0 + t * rect_width_1
        rect_x = x - rect_width / 2
        rect_y = y - self.height / 2
        pygame.draw.rect(
            buffer_surface,
            "#117D10",
            (rect_x, rect_y, rect_width, self.height),
            border_radius=int(self.height / 2),
        )
        circle_x = rect_x + self.height / 2
        pygame.draw.circle(buffer_surface, "#56A820", (circle_x, y), self.height / 2)

        buffer_surface.blit(
            self.icon,
            (circle_x - self.icon.get_width() / 2, y - self.icon.get_height() / 2),
        )

        text_x = (x - self.width / 2 + self.height) + (
            self.width - self.height - self.text_surface.get_width()
        ) / 2
        text_y = rect_y + (self.height - self.text_surface.get_height()) / 2
        text_alpha = int(255 * max(0, (t - 0.8) / 0.2))
        self.text_surface.set_alpha(text_alpha)
        buffer_surface.blit(self.text_surface, (text_x, text_y))

        pygame.draw.rect(
            buffer_surface,
            "#0e420b",
            (rect_x, rect_y, rect_width, self.height),
            width=3,
            border_radius=int(self.height / 2),
        )
        pygame.draw.circle(
            buffer_surface, "#0e420b", (circle_x, y), self.height / 2, width=3
        )

        buffer_surface.set_alpha(int(255 * alpha))
        screen.blit(buffer_surface)


def game(text_queue: Queue, stop_queue: Queue):
    pygame.init()
    font = pygame.font.Font("./big_blue_term.ttf", 35)
    microphone = pygame.image.load("microphone.png")
    clock = pygame.time.Clock()

    width, height = 1600, 200
    width *= 0.5
    height *= 0.5
    screen = pygame.display.set_mode((width, height), pygame.NOFRAME)
    dt = 0

    done = False
    t = 0

    cheevo = None

    while not done:
        if not stop_queue.empty():
            break
        screen.fill("#0000ff")

        if not text_queue.empty():
            text = text_queue.get()
            cheevo = Achievement(width, height, text, font, microphone)
            cheevo.start()
        if cheevo:
            if cheevo.done:
                cheevo = None
            else:
                cheevo.render(screen)

        pygame.display.flip()
        dt = clock.tick(60)

    stop_queue.put(True)
    pygame.quit()


def terminal_input(text_queue: Queue, stop_queue: Queue):
    text = input("Enter achievement text or 'stop' to end the program:\n")
    if not text:
        return True
    if text.lower() == "stop":
        stop_queue.put(True)
        return False
    text_queue.put(text)
    return True


def main():
    text_queue = Queue()
    stop_queue = Queue()
    game_thread = Process(target=game, args=[text_queue, stop_queue])
    game_thread.start()
    while True:
        running = terminal_input(text_queue, stop_queue)
        if not running:
            break


if __name__ == "__main__":
    main()

// IrisStoryViewerViewController.m
#import "IrisStoryViewerViewController.h"
#import "IrisTheme.h"
#import "IrisData.h"

@interface IrisStoryViewerViewController ()

@property (nonatomic, strong) IrisStory *story;
@property (nonatomic, assign) NSInteger currentStoryIndex;
@property (nonatomic, strong) UIImageView *storyImageView;
@property (nonatomic, strong) UIView *progressBar;
@property (nonatomic, strong) UIImageView *avatarImageView;
@property (nonatomic, strong) UILabel *usernameLabel;
@property (nonatomic, strong) UILabel *timeLabel;
@property (nonatomic, strong) UIButton *closeButton;

@end

@implementation IrisStoryViewerViewController

- (instancetype)initWithStory:(IrisStory *)story {
    self = [super init];
    if (self) {
        _story = story;
        _currentStoryIndex = [[IrisData sharedData].stories indexOfObject:story];
        if (_currentStoryIndex == NSNotFound) _currentStoryIndex = 0;
    }
    return self;
}

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = [UIColor blackColor];
    
    // Background story image
    self.storyImageView = [[UIImageView alloc] initWithFrame:self.view.bounds];
    self.storyImageView.contentMode = UIViewContentModeScaleAspectFill;
    self.storyImageView.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    [self.view addSubview:self.storyImageView];
    
    // Top Progress bar
    self.progressBar = [[UIView alloc] initWithFrame:CGRectMake(12, 44, self.view.bounds.size.width - 24, 3)];
    self.progressBar.backgroundColor = [[IrisTheme sharedTheme] accentVioletColor];
    self.progressBar.layer.cornerRadius = 1.5;
    [self.view addSubview:self.progressBar];
    
    // User info header
    self.avatarImageView = [[UIImageView alloc] initWithFrame:CGRectMake(16, 56, 36, 36)];
    self.avatarImageView.layer.cornerRadius = 18.0;
    self.avatarImageView.layer.masksToBounds = YES;
    [self.view addSubview:self.avatarImageView];
    
    self.usernameLabel = [[UILabel alloc] initWithFrame:CGRectMake(60, 56, 180, 20)];
    self.usernameLabel.font = [UIFont systemFontOfSize:14 weight:UIFontWeightBold];
    self.usernameLabel.textColor = [UIColor whiteColor];
    [self.view addSubview:self.usernameLabel];
    
    self.timeLabel = [[UILabel alloc] initWithFrame:CGRectMake(60, 76, 180, 16)];
    self.timeLabel.font = [UIFont systemFontOfSize:11 weight:UIFontWeightRegular];
    self.timeLabel.textColor = [UIColor colorWithWhite:0.8 alpha:1.0];
    [self.view addSubview:self.timeLabel];
    
    // Close button
    self.closeButton = [UIButton buttonWithType:UIButtonTypeCustom];
    self.closeButton.frame = CGRectMake(self.view.bounds.size.width - 48, 56, 36, 36);
    [self.closeButton setImage:[IrisTheme iconNamed:@"close" size:CGSizeMake(22, 22) color:[UIColor whiteColor] filled:NO] forState:UIControlStateNormal];
    [self.closeButton addTarget:self action:@selector(dismissSelf) forControlEvents:UIControlEventTouchUpInside];
    [self.view addSubview:self.closeButton];
    
    // Tap gestures for left (previous) and right (next) navigation
    UITapGestureRecognizer *tapGesture = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(handleScreenTap:)];
    [self.view addGestureRecognizer:tapGesture];
    
    [self displayStoryAtIndex:self.currentStoryIndex];
}

- (void)displayStoryAtIndex:(NSInteger)index {
    if (index < 0 || index >= (NSInteger)[IrisData sharedData].stories.count) {
        [self dismissSelf];
        return;
    }
    self.currentStoryIndex = index;
    IrisStory *s = [IrisData sharedData].stories[index];
    s.viewed = YES;
    self.story = s;
    
    self.usernameLabel.text = s.username;
    self.timeLabel.text = s.timestamp;
    
    self.avatarImageView.image = [IrisData imageForKey:s.avatar
                                                  size:CGSizeMake(36, 36)
                                                 title:[s.username uppercaseString]
                                              subtitle:@""];
    
    self.storyImageView.image = [IrisData imageForKey:s.imageKey
                                                 size:self.view.bounds.size
                                                title:s.username
                                             subtitle:@"Iris Story"];
}

- (void)handleScreenTap:(UITapGestureRecognizer *)gesture {
    CGPoint pt = [gesture locationInView:self.view];
    if (pt.x < self.view.bounds.size.width * 0.35) {
        // Tapped left: Previous story
        if (self.currentStoryIndex > 0) {
            [self displayStoryAtIndex:self.currentStoryIndex - 1];
        }
    } else {
        // Tapped right: Next story
        if (self.currentStoryIndex < (NSInteger)[IrisData sharedData].stories.count - 1) {
            [self displayStoryAtIndex:self.currentStoryIndex + 1];
        } else {
            [self dismissSelf];
        }
    }
}

- (void)dismissSelf {
    [self dismissViewControllerAnimated:YES completion:nil];
}

@end
